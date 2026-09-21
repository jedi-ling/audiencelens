# -*- coding: utf-8 -*-
"""Markdown -> PDF，面向中文文档（商业计划书 / 对外材料）。

为什么不用 pandoc / weasyprint：本机都没有，且它们各自还要拖 LaTeX 或 GTK 依赖。
reportlab + 系统自带的微软雅黑就够，不引入新的运行时依赖。

CJK 三个必须处理的点：
  1. 字体——雅黑 msyh.ttc 是 TTC 集合，必须给 subfontIndex，否则加载失败；
  2. 断行——Paragraph 必须 wordWrap='CJK'，否则中文整段不折行直接溢出页面；
  3. 字形缺失——emoji（对勾 / 彩色圆点等）雅黑没有对应字形，会渲染成空心方框，
     所以映射成有字形的几何符号，并用颜色保留原本的语义。
"""

import html
import io
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

FONTS = "C:/Windows/Fonts/"

# 打印用配色：品牌青 #00e5ff 在白纸上几乎看不见，这里降饱和到可读的深青
INK = colors.HexColor("#1a1d24")
INK_STRONG = colors.HexColor("#0c0e14")
INK_DIM = colors.HexColor("#5a6376")
ACCENT = colors.HexColor("#00788c")
RULE = colors.HexColor("#d8dee6")
TH_BG = colors.HexColor("#f2f5f7")
CODE_BG = colors.HexColor("#eef2f5")

OK_C = colors.HexColor("#1a7f4b")
WARN_C = colors.HexColor("#b5730a")
CRIT_C = colors.HexColor("#c0392b")

# emoji -> (替代字形, 颜色)。雅黑没有 emoji 字形，不替换会渲染成空心方框。
# 替代字形本身也必须在雅黑 cmap 里——曾经用 ✓/✕/◑ 替换，结果它们同样缺字形，
# 等于把一种空框换成了另一种。下面这几个都已对 msyh.ttc 的 cmap 逐一验证。
SYMBOL_MAP = {
    u"✅": (u"√", OK_C),        # 对勾 -> 根号形对勾
    u"🟢": (u"●", OK_C),    # 绿圆 -> 实心圆
    u"🟡": (u"◎", WARN_C),  # 黄圆 -> 同心圆（进行中）
    u"🟠": (u"◆", WARN_C),  # 橙圆 -> 实心菱形
    u"🔴": (u"●", CRIT_C),  # 红圆 -> 实心圆
    u"❌": (u"×", CRIT_C),      # 叉 -> 乘号
    u"⚪": (u"○", INK_DIM),     # 白圆 -> 空心圆
}


def missing_glyphs(text, font_name="CN"):
    """返回 text 中该字体没有字形的字符集合。

    存在的意义：字形缺失不会报错，只会静默渲染成空框——PDF 生成"成功"、
    打开一看全是方块。这个检查让它在构建期就暴露。
    """
    face = pdfmetrics.getFont(font_name).face
    cmap = getattr(face, "charToGlyph", None)
    if not cmap:
        return set()
    skip = ("\r", "\n", "\t")
    return set(c for c in set(text)
               if c not in skip and ord(c) not in cmap)


def register_fonts():
    def reg(name, filename, idx=None):
        path = os.path.join(FONTS, filename)
        if not os.path.exists(path):
            return False
        if idx is not None:
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
        else:
            pdfmetrics.registerFont(TTFont(name, path))
        return True

    if not reg("CN", "msyh.ttc", 0):
        raise RuntimeError("找不到微软雅黑 msyh.ttc，无法排中文")
    if not reg("CN-Bold", "msyhbd.ttc", 0):
        reg("CN-Bold", "msyh.ttc", 0)
    if not reg("Mono", "consola.ttf"):
        reg("Mono", "cour.ttf")
    if not reg("Mono-Bold", "consolab.ttf"):
        reg("Mono-Bold", "courbd.ttf")
    pdfmetrics.registerFontFamily("CN", normal="CN", bold="CN-Bold",
                                  italic="CN", boldItalic="CN-Bold")
    pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold")


def inline(text):
    """Markdown 行内语法 -> reportlab 标记。

    顺序有讲究：先抽出符号占位，再 HTML 转义，再把行内代码摘出来保护，
    最后才处理强调——否则代码里的星号会被当成强调标记。
    """
    for emo, pair in SYMBOL_MAP.items():
        glyph, col = pair
        text = text.replace(emo, u"\x00%s\x01%s\x02" % (col.hexval()[2:], glyph))

    text = html.escape(text, quote=False)

    holds = []

    def hold(m):
        holds.append(m.group(1))
        return u"\x10%d\x11" % (len(holds) - 1)

    text = re.sub(r"`([^`]+)`", hold, text)

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: u'<link href="%s" color="#00788c">%s</link>'
                  % (m.group(2), m.group(1)), text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", text)

    def unhold(m):
        code = holds[int(m.group(1))]
        # 不要在这里加 &nbsp; 当内边距：U+00A0 在 wordWrap='CJK' 下会让
        # reportlab 的断行器错算片段宽度，吃掉相邻空格并把文字叠印在一起。
        return (u'<font face="Mono" size="8.4" backColor="#eef2f5">%s</font>'
                % code)

    text = re.sub(r"\x10(\d+)\x11", unhold, text)
    text = re.sub(r"\x00([0-9a-fA-F]{6})\x01(.)\x02",
                  lambda m: u'<font color="#%s">%s</font>' % (m.group(1), m.group(2)),
                  text)
    return text


def build_styles():
    base = dict(fontName="CN", textColor=INK, wordWrap="CJK", alignment=TA_LEFT)
    S = {}
    S["title"] = ParagraphStyle("title", fontName="CN-Bold", textColor=INK_STRONG,
                                fontSize=21, leading=29, spaceAfter=2, wordWrap="CJK")
    S["h1"] = ParagraphStyle("h1", fontName="CN-Bold", textColor=INK_STRONG,
                             fontSize=15.5, leading=22, spaceBefore=15, spaceAfter=7,
                             wordWrap="CJK")
    S["h2"] = ParagraphStyle("h2", fontName="CN-Bold", textColor=INK_STRONG,
                             fontSize=13, leading=19, spaceBefore=13, spaceAfter=6,
                             wordWrap="CJK")
    S["h3"] = ParagraphStyle("h3", fontName="CN-Bold", textColor=ACCENT,
                             fontSize=11.2, leading=16.5, spaceBefore=11, spaceAfter=5,
                             wordWrap="CJK")
    S["h4"] = ParagraphStyle("h4", fontName="CN-Bold", textColor=INK_STRONG,
                             fontSize=10, leading=15, spaceBefore=9, spaceAfter=4,
                             wordWrap="CJK")
    S["body"] = ParagraphStyle("body", fontSize=9.3, leading=15.2, spaceAfter=6, **base)
    # bulletFontName 不设就是 Helvetica，和正文雅黑并排会明显不齐
    S["bullet"] = ParagraphStyle("bullet", fontSize=9.3, leading=15, spaceAfter=3,
                                 leftIndent=11, bulletIndent=1,
                                 bulletFontName="CN", bulletFontSize=9.3, **base)
    S["quote"] = ParagraphStyle("quote", fontName="CN", fontSize=8.8, leading=14.2,
                                spaceAfter=5, textColor=INK_DIM, wordWrap="CJK",
                                alignment=TA_LEFT)
    S["cell"] = ParagraphStyle("cell", fontName="CN", fontSize=8.1, leading=12.3,
                               textColor=INK, wordWrap="CJK")
    S["cellh"] = ParagraphStyle("cellh", fontName="CN-Bold", fontSize=8.1, leading=12.3,
                                textColor=INK_STRONG, wordWrap="CJK")
    S["code"] = ParagraphStyle("code", fontName="Mono", fontSize=7.9, leading=11.4,
                               textColor=INK, backColor=CODE_BG, borderPadding=6,
                               leftIndent=2, spaceAfter=7)
    return S


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_sep(line):
    return bool(re.match(r"^\|[\s:\-|]+\|?$", line.strip())) and "-" in line


def make_table(rows, avail, S):
    header = rows[0]
    body = rows[1:]
    ncol = len(header)

    weights = []
    for i in range(ncol):
        lens = [len(header[i])]
        for r in body:
            lens.append(len(r[i]) if i < len(r) else 0)
        weights.append(max(max(lens), 4))
    total = float(sum(weights))
    widths = [max(avail * w / total, 24) for w in weights]
    scale = avail / sum(widths)
    widths = [w * scale for w in widths]

    data = [[Paragraph(inline(c), S["cellh"]) for c in header]]
    for r in body:
        r = (list(r) + [""] * ncol)[:ncol]
        data.append([Paragraph(inline(c), S["cell"]) for c in r])

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TH_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def convert(md_path, pdf_path, doc_title):
    register_fonts()
    S = build_styles()

    text = io.open(md_path, encoding="utf-8").read().replace("\r\n", "\n")
    lines = text.split("\n")

    margin_l = margin_r = 18 * mm
    margin_t = 17 * mm
    margin_b = 16 * mm
    avail = A4[0] - margin_l - margin_r

    story = []
    i = 0
    n = len(lines)
    title_done = False

    while i < n:
        s = lines[i].rstrip()

        if not s.strip():
            i += 1
            continue

        if s.lstrip().startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            body = html.escape("\n".join(buf), quote=False)
            body = body.replace(" ", "&nbsp;").replace("\n", "<br/>")
            story.append(Paragraph(body, S["code"]))
            continue

        if s.startswith("|") and i + 1 < n and is_sep(lines[i + 1]):
            rows = [split_row(s)]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            story.append(Spacer(1, 3))
            story.append(make_table(rows, avail, S))
            story.append(Spacer(1, 8))
            continue

        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", s):
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.5, color=RULE,
                                    spaceBefore=0, spaceAfter=8))
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            txt = m.group(2)
            if lvl == 1 and not title_done:
                title_done = True
                story.append(Paragraph(inline(txt), S["title"]))
                story.append(HRFlowable(width="100%", thickness=1.1, color=ACCENT,
                                        spaceBefore=7, spaceAfter=12))
            else:
                key = {1: "h1", 2: "h1", 3: "h2", 4: "h3"}.get(lvl, "h4")
                story.append(Paragraph(inline(txt), S[key]))
            i += 1
            continue

        if s.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]).rstrip())
                i += 1
            chunks = []
            cur = []
            for b in buf:
                if b.strip():
                    cur.append(b.strip())
                elif cur:
                    chunks.append(" ".join(cur))
                    cur = []
            if cur:
                chunks.append(" ".join(cur))
            inner = [Paragraph(inline(c), S["quote"]) for c in chunks]
            t = Table([[inner]], colWidths=[avail], hAlign="LEFT")
            t.setStyle(TableStyle([
                ("LINEBEFORE", (0, 0), (0, -1), 1.6, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(t)
            story.append(Spacer(1, 7))
            continue

        m = re.match(r"^(\s*)[-*]\s+(.*)$", s)
        if m:
            depth = len(m.group(1)) // 2
            st = ParagraphStyle("b%d" % depth, parent=S["bullet"],
                                leftIndent=11 + depth * 12,
                                bulletIndent=1 + depth * 12)
            story.append(Paragraph(inline(m.group(2)), st,
                                   bulletText=u"\u2013" if depth else u"\u2022"))
            i += 1
            continue

        m = re.match(r"^(\s*)(\d+)\.\s+(.*)$", s)
        if m:
            depth = len(m.group(1)) // 2
            st = ParagraphStyle("o%d" % depth, parent=S["bullet"],
                                leftIndent=15 + depth * 12,
                                bulletIndent=1 + depth * 12)
            story.append(Paragraph(inline(m.group(3)), st,
                                   bulletText="%s." % m.group(2)))
            i += 1
            continue

        buf = [s.strip()]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(\s*([-*]|\d+\.)\s|#{1,6}\s|>|\||```|-{3,}\s*$)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline(" ".join(buf)), S["body"]))

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("CN", 7.3)
        canvas.setFillColor(INK_DIM)
        canvas.drawString(margin_l, 9 * mm, doc_title)
        canvas.drawRightString(A4[0] - margin_r, 9 * mm, "%d" % doc.page)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(margin_l, 12.5 * mm, A4[0] - margin_r, 12.5 * mm)
        canvas.restoreState()

    doc = BaseDocTemplate(pdf_path, pagesize=A4,
                          leftMargin=margin_l, rightMargin=margin_r,
                          topMargin=margin_t, bottomMargin=margin_b,
                          title=doc_title, author="ShanYi Studio")
    frame = Frame(margin_l, margin_b, avail, A4[1] - margin_t - margin_b, id="f")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])
    doc.build(story)

    # 构建后自检：正文里若还有字体没有的字形，PDF 会静默渲染成空框。
    # 这里主动报出来，而不是等人肉发现。
    probe = text
    for emo, pair in SYMBOL_MAP.items():
        probe = probe.replace(emo, pair[0])
    miss = missing_glyphs(probe)
    if miss:
        detail = " ".join("U+%04X(%s)" % (ord(c), c) for c in sorted(miss))
        sys.stderr.write("[warn] 以下字符在字体中无字形，PDF 里会显示为空框: %s\n"
                         % detail)
    return pdf_path


def _argv_text(v):
    """Windows GBK 控制台下 sys.argv 里的中文会被按本地码页解码而损坏。
    这里尝试按本地码页还原成字节再按 UTF-8 解，失败就原样返回。"""
    try:
        return v.encode(sys.getfilesystemencoding(), "strict").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return v


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2]
    title = _argv_text(sys.argv[3]) if len(sys.argv) > 3 else os.path.basename(src)
    convert(src, dst, title)
    print("OK %s %d bytes" % (dst, os.path.getsize(dst)))

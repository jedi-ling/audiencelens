# -*- coding: utf-8 -*-
"""落地页**英文版**（landing-body.en.html）的能力声明与结构核对。

这是 test_landing_capability_claims.py 的英文对应件，由 docs/I18N_CONTRACT.md §4.4
点名为"不可省"的交付物。为什么不可省：中文原件之所以不就地翻译，正是因为
test_landing_capability_claims.py:96-105 在关键短语找不到时走 pytest.skip 而不是
fail——就地翻译会让 6 条"文案 ↔ 实现"断言全部静默跳过而测试全绿。
如果只新建了 landing-body.en.html 却不配这一套断言，等于把刚刚避开的那个洞
换一种语言重新挖一遍：英文版说了什么、代码里有没有，没有任何东西会管。

三类检查：

  1. test_en_claim_tracks_zh_and_has_a_real_implementation
     中文原件还在声称某个机制 ⇒ 英文版必须同样声称 ⇒ 代码里必须真有这件事。
     **门是中文侧**：中文不再声称了（整条声明被删）就一起跳过，
     所以这条测试不会拦住"两份一起删掉某个说法"的正常操作；
     拦的是"英文版漂了/漏译了/翻软了"——那是静默失真，没人看得见。

     和中文那条的差别：中文侧短语全找不到时它 skip（措辞润色不该叫狼）；
     这里在中文侧还在声称时**直接 fail**，因为英文版是中文版的对应件，
     "中文有、英文没有"永远是缺陷，不是一次合法的内容决策。

  2. test_removed_claims_stay_removed_in_english
     历史上因"引擎里根本没有"被删掉的说法（ROUND 3 / 分歧度 / 说服力分 /
     红队对抗模式），英文版也不许以英文形态写回来。

  3. test_en_body_is_structurally_parallel
     数字与 DOM 钩子必须与中文原件一致。
     数字：中文那侧由 test_public_claims.py 对着 src/personas 现算值核，
     这里只核"英文 == 中文"，一条链就闭合了，不必在两个文件里各写一套推导。
     DOM 钩子：LandingPage.tsx 的 JS 按 #heroAsk / #heroStageMount / .reveal /
     .num[data-target] / .debate-flip 这些选择器挂事件与观察器。英文版少一个
     选择器不会报任何错，只会让英文首页少一段交互——最典型的静默失败。
"""

import io
import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANDING_DIR = os.path.join(REPO_ROOT, "web", "frontend", "src", "pages", "landing")
LANDING_ZH = os.path.join(LANDING_DIR, "landing-body.html")
LANDING_EN = os.path.join(LANDING_DIR, "landing-body.en.html")


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def _strip_comments(text):
    """HTML 注释整段剥掉。

    两个理由：(a) 注释里原样引用了那些**禁用词**（"曾经这里写的是『实时交叉质询 /
    ROUND 3 / 分歧度 / 说服力』"），不剥的话第 2 类检查会被它要保护的那段注释
    自己触发；(b) 本文件顶部的说明注释里也写着 .reveal / .num[data-target]
    这些选择器名，会把第 3 类的计数算多。中文那条测试踩过 (a)，这里两条都踩得到。
    """
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


# (声明名, 中文原件里的关键短语, 英文版里的关键短语, [(事实源文件, 标识符), ...])
#
# 中文短语一律取自 test_landing_capability_claims.py 的 CLAIMS，逐字对齐——
# 那边改了措辞、这边没跟上时，中文短语找不到 → 本条跳过，不会变成假红。
# 事实源同样用"文件 + 标识符"，理由见中文那条测试：行号会随无关改动漂移。
CLAIMS = [
    (
        "证据三级标注（direct / inferred / gap）",
        ["direct（直接观察）", "inferred（合理推断）", "gap（信息缺口）"],
        [
            "direct (observed in your material)",
            "inferred (reasonable inference)",
            "gap (missing information)",
        ],
        [("src/runner/persona_agent.py", '_EVIDENCE_LEVELS = ("direct", "inferred", "gap")')],
    ),
    (
        "推断占比超过 40% 会被标记为推断过度",
        ["推断占比超过 40%", "推断过度"],
        ["40% inferred", "over-inference"],
        [("src/runner/validator.py", "推断过度")],
    ),
    (
        "Top-3 争议点交叉质询",
        ["Top-3 争议点交叉质询"],
        ["top 3 disagreements"],
        [("src/runner/cross_exam.py", "def ")],
    ),
    (
        "改票由代码判定、阈值写在开源配置里",
        ["改票由代码判定", "阈值写在开源配置里"],
        ["Vote changes are decided by code", "open-source config file"],
        [("src/runner/cross_exam.py", "confidence_change_threshold")],
    ),
    (
        "伦理护栏：身份与行为解耦，人口统计字段注入前剥离",
        ["身份与行为解耦", "在注入提示词前会被剥离"],
        ["Identity is decoupled from behavior", "stripped before anything is injected into the prompt"],
        [
            ("src/runner/persona_agent.py", "CORE_FIELDS"),
            ("src/runner/validator.py", "check_identity_behavior_decoupling"),
        ],
    ),
    (
        "预测留档 + 真人结果回填 + 人格历史准确率（low_confidence 标注）",
        ["真人结果回填", "low_confidence"],
        ["real outcomes filled back in", "low_confidence"],
        [
            ("web/backend/app/services/validation_service.py", "low_confidence"),
            ("web/backend/app/api/platform.py", "/ledger/hit-rate"),
        ],
    ),
]


def test_en_landing_body_exists():
    """先确认文件在。缺了它英文用户拿到的是一个空白首页，而 React 不会报错。"""
    assert os.path.exists(LANDING_EN), (
        f"{LANDING_EN} 不存在。LandingPage.tsx 按 ui_lang 选正文，"
        "少了这份文件构建期就会挂（?raw import 找不到模块）。"
    )


@pytest.mark.parametrize(
    "name,zh_phrases,en_phrases,sources", CLAIMS, ids=[c[0] for c in CLAIMS]
)
def test_en_claim_tracks_zh_and_has_a_real_implementation(name, zh_phrases, en_phrases, sources):
    zh = _read(LANDING_ZH)
    en = _read(LANDING_EN)

    if not any(p in zh for p in zh_phrases):
        pytest.skip(
            f"中文原件当前没有『{name}』相关文案（可能已改写或删除）——"
            "两份一起删是合法操作；若只是改了措辞，请同时更新本测试与"
            "test_landing_capability_claims.py 的关键短语。"
        )

    missing = [p for p in en_phrases if p not in en]
    assert not missing, (
        f"中文落地页声称『{name}』，但 landing-body.en.html 里找不到对应说法：{missing}。\n"
        "英文版是中文版的对应件，「中文有、英文没有」永远是缺陷：\n"
        "  · 漏译 → 英文用户看不到这个卖点；\n"
        "  · 翻软了/翻成了别的意思 → 英文版在说一件代码里没有的事，而中文版的\n"
        "    断言完全拦不到它。\n"
        "确实要改英文措辞：改完把新短语同步进本测试，别把断言删掉。"
    )

    for rel_path, marker in sources:
        abs_path = os.path.join(REPO_ROOT, rel_path)
        assert os.path.exists(abs_path), (
            f"英文落地页声称『{name}』，但事实源文件 {rel_path} 不存在了。"
            "要么这个能力被删了（两份文案都得同步删），要么实现搬了家（更新事实源路径）。"
        )
        assert marker in _read(abs_path), (
            f"英文落地页声称『{name}』，但 {rel_path} 里已经找不到 `{marker}`。"
            "确认这个能力是否还在：还在就更新标识符，不在就把两份文案都改掉。"
        )


def test_removed_claims_stay_removed_in_english():
    """历史上被删掉的说法，换成英文也不许写回来。

    禁用词必须是"指标形态"，不能是裸词——中文那条测试记录过教训：
    最初禁的是裸的「说服力」，命中了 SaaS 定价页那张卡上「CTA 说服力」
    （说的是**用户自己定价页**的说服力，完全合法）。对正常文案叫狼的测试
    活不过三次。所以这里禁的是 "persuasiveness score" 而不是 "persuasive"，
    英文版写的是 "how convincing the CTA is"，同一个意思、不碰指标形态。
    """
    en = _strip_comments(_read(LANDING_EN)).lower()
    forbidden = [
        # cross_exam.py 只跑一轮，没有轮次概念
        ("round 3", "引擎只跑一轮交叉质询，没有第三轮"),
        ("round three", "同上"),
        # 引擎不产出这两个指标
        ("disagreement score", "引擎不产出『分歧度』这个指标"),
        ("divergence score", "同上，换个词也没有"),
        ("persuasiveness score", "引擎不计算说服力分（描述用户材料的 CTA 说服力不在此列）"),
        ("persuasion score", "同上"),
        # CLI 的 red-team-audience 参数收下就丢，不影响任何一次评审
        ("red-team mode", "引擎里没有红队模式，也没有红队人格包"),
        ("red team mode", "同上"),
        # 引擎只跑一轮，不是多轮辩论；LandingPage.tsx:154-162 的注释专门警告过
        ("multi-round debate", "只有一轮反驳，不是多轮辩论"),
        ("live debate", "cross_exam 不是实时辩论，is_live_debate 恒 False"),
    ]
    for phrase, why in forbidden:
        assert phrase not in en, (
            f"landing-body.en.html 里出现了『{phrase}』——{why}。"
            "这个说法在中文侧被删过一次（见 landing-body.html 里的注释），"
            "用英文写回来同样是虚假宣传。"
        )


# LandingPage.tsx 的 useEffect 里逐个查这些选择器挂事件 / 观察器 / 3D 舞台。
# 少一个不会抛错，只会让英文首页少一段交互——所以只能靠断言守。
# 形态写成"出现在 HTML 里的字面片段"，而不是解析 DOM：这份 HTML 是片段
# （没有 <html>/<body>），任何解析器都得先补壳，补壳本身就会引入分歧。
REQUIRED_HOOKS = [
    ('id="heroStageMount"', "hero 3D 舞台的挂载点，缺了英文首页没有粒子背景"),
    ('id="heroAsk"', "首屏输入条的 form，缺了回车提交不跳 /ask"),
    ('id="heroAskInput"', "首屏输入条的 input，缺了提交的永远是空串"),
    ('class="hero-bg-video"', "全页视频背景，缺了 reduced-motion / 窄屏那段省流量逻辑无处生效"),
    ('class="debate-card reveal"', "争议点示意卡，缺了 stagger 入场整段不跑"),
    ('class="debate-msg oppose"', "stagger 的第 1 个目标"),
    ('class="debate-flip"', "stagger 的第 2 个目标"),
    ('class="debate-msg agree"', "stagger 的第 3 个目标"),
    ('class="proof-jump" href="#numbers"', "hero 里指向 STATS 区的锚点，靠 # 平滑滚动那条分支"),
]

# 中英必须逐字相等的结构性计数。
REQUIRED_SECTION_IDS = [
    "top", "pain", "usecases", "how", "flow", "capabilities", "compare", "numbers", "try",
]


def test_en_body_is_structurally_parallel():
    zh = _strip_comments(_read(LANDING_ZH))
    en = _strip_comments(_read(LANDING_EN))

    for hook, why in REQUIRED_HOOKS:
        assert hook in en, (
            f"landing-body.en.html 里缺少 `{hook}`（{why}）。\n"
            "LandingPage.tsx 的 JS 是两份正文共用的：选择器对不上时 "
            "querySelector 返回 null，代码里全是可选链，"
            "**不报错、不白屏**，只是那段交互在英文界面上不存在。"
        )

    for sid in REQUIRED_SECTION_IDS:
        assert f'id="{sid}"' in en, (
            f"landing-body.en.html 缺 section id=\"{sid}\"。"
            "页内锚点与 landing.css 的分区样式都按 id 走。"
        )

    # --- 数字：英文 == 中文。中文那侧由 test_public_claims.py 对着仓库真值核 ---
    targets = lambda s: re.findall(r'data-target="(\d+)"', s)
    assert targets(en) == targets(zh), (
        f"STATS 区的数字对不上：中文 {targets(zh)} / 英文 {targets(en)}。\n"
        "人格数 / 任务类型数 / Pack 数是对外声称值，中文那侧由 "
        "test_public_claims.py 对着 src/personas 与 task_types.py 现算值核；"
        "英文这侧只核『与中文相等』。改一边漏一边 = 英文用户看到过期数字。"
    )

    # 头像行的"+N"是**隐式**人格计数（画出来的头像数 + N = 总数），
    # 任何"捞总数"的正则都捞不到它——test_public_claims.py 为它单独写了一条测试，
    # 这里同样单独核，且核的是"英文与中文的构成完全一致"。
    def avatar_shape(src):
        block = re.search(r'<div class="avatars">(.*?)</div>', src, re.S)
        assert block, "找不到 .avatars 区块"
        spans = re.findall(r"<span[^>]*>([^<]+)</span>", block.group(1))
        drawn = [s for s in spans if not s.strip().startswith("+")]
        overflow = [s for s in spans if s.strip().startswith("+")]
        return len(drawn), overflow

    assert avatar_shape(en) == avatar_shape(zh), (
        f"头像行的构成对不上：中文 {avatar_shape(zh)} / 英文 {avatar_shape(en)}。"
        "溢出数 = 人格总数 − 画出来的头像数，是隐式计数，"
        "72 人格上线后中文侧的 +63 就一直错着没人发现——英文侧不要重演。"
    )

    # 测试数那一格必须带统计日期。中文侧的规矩（test_public_claims.py::
    # test_test_counts_are_stated_once_and_dated）是"全页只写一处并带日期"，
    # 英文侧同样不许出现第二个测试数，也不许把 skipped 抹掉写成 all green。
    assert re.search(r"2026-08-02", en), "英文 STATS 区的测试数缺统计日期"
    assert re.search(r"\b8\b[^<]*skipped", en), (
        "英文 STATS 区没写 skipped 数。中文原件的注释明写：不要写成"
        "『全绿』抹掉那 8 项 skipped——英文侧同理，all green 是假绿。"
    )
    assert en.lower().count("tests passing") == 1, (
        "英文落地页出现了不止一处测试数声明。测试数会随开发漂移，"
        "全页只允许 STATS 区写一处（同中文侧的规矩），多写一处就会有一处过期。"
    )

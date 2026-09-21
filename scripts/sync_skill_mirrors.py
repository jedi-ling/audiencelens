# -*- coding: utf-8 -*-
"""把 `.agents/skills/synthetic-playtest/`（唯一权威源）整棵同步到两个镜像目录。

为什么需要它：技能目录一式三份（`.agents/` 权威、`.claude/` 与 `.trae/` 镜像），
而 CI 只比过 SKILL.md 的 frontmatter name 与 `## Phase` 条数——那两项恰好是最不会
变的部分。结果 `.trae/` 在无人察觉的情况下漂了 7 个同名文件：两个 persona 包里的
YAML 引号修法不同、mobile-f2p 多出两个 id 与 family-casual 撞号、persona-prompt.md
少一段 ARTIFACT MATERIALS。镜像漂了就等于"同一个技能在不同工具里跑出不同结果"。

现在 CI 改成整目录递归比对（见 `.github/workflows/ci.yml` 的 skill-consistency），
唯一允许的差异是镜像横幅那两行。改完权威源后跑一次本脚本即可：

    py -3.11 scripts/sync_skill_mirrors.py          # 写入镜像
    py -3.11 scripts/sync_skill_mirrors.py --check  # 只检查，不写（CI 用的是 shell 版）
"""

from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL = os.path.join(REPO_ROOT, ".agents", "skills", "synthetic-playtest")
MIRRORS = (
    os.path.join(REPO_ROOT, ".claude", "skills", "synthetic-playtest"),
    os.path.join(REPO_ROOT, ".trae", "skills", "synthetic-playtest"),
)

BANNER_COMMENT = "<!-- mirror of .agents/skills/synthetic-playtest/SKILL.md; do not edit here -->"
BANNER_NOTICE = (
    "> **Mirror Notice**: This file is a read-only mirror. The canonical source is at "
    "`.agents/skills/synthetic-playtest/SKILL.md`. Any edits must be made there."
)


def _rel_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(out)


def _lf(blob: bytes) -> bytes:
    """比较与写入一律按 LF 口径。

    开发机 core.autocrlf=true：已跟踪的文件签出成 CRLF，而新加进来的文件还是 LF，
    于是同一份内容会因为换行不同被判成"漂移"。那种假阳性最坏的后果不是多同步一次，
    而是有人因此认为这个检查不可信，转手把它调松。仓库侧另有 .gitattributes
    把三棵技能树钉成 eol=lf，这里是同一条口径的另一半。
    """
    return blob.replace(b"\r\n", b"\n")


def _with_banner(text):
    """在 frontmatter 之后插入 HTML 注释横幅，在首个一级标题之后插入可读提示。"""
    lines = text.split("\n")
    if BANNER_COMMENT in lines:
        return text
    out = []
    inserted_comment = False
    inserted_notice = False
    fence = 0
    for line in lines:
        out.append(line)
        if not inserted_comment and line.strip() == "---":
            fence += 1
            if fence == 2:  # frontmatter 的闭合分隔线
                out.extend(["", BANNER_COMMENT])
                inserted_comment = True
            continue
        if inserted_comment and not inserted_notice and line.startswith("# "):
            out.extend(["", BANNER_NOTICE])
            inserted_notice = True
    return "\n".join(out)


def sync(check_only=False):
    assert os.path.isdir(CANONICAL), f"权威源不存在：{CANONICAL}"
    canonical_files = _rel_files(CANONICAL)
    drift = []

    for mirror in MIRRORS:
        rel_mirror = os.path.relpath(mirror, REPO_ROOT).replace(os.sep, "/")

        # 1) 镜像里多出来的文件一律删掉——"多一个文件"同样是漂移
        for rel in _rel_files(mirror) if os.path.isdir(mirror) else []:
            if rel not in canonical_files:
                drift.append(f"{rel_mirror}/{rel}: 权威源里没有这个文件")
                if not check_only:
                    os.remove(os.path.join(mirror, rel.replace("/", os.sep)))

        # 2) 逐个文件写过去（SKILL.md 额外加横幅）
        for rel in canonical_files:
            src = os.path.join(CANONICAL, rel.replace("/", os.sep))
            dst = os.path.join(mirror, rel.replace("/", os.sep))
            with open(src, "rb") as f:
                raw = _lf(f.read())
            if rel == "SKILL.md":
                payload = _with_banner(raw.decode("utf-8")).encode("utf-8")
            else:
                payload = raw
            old = None
            if os.path.isfile(dst):
                with open(dst, "rb") as f:
                    old = _lf(f.read())
            if old == payload:
                continue
            drift.append(f"{rel_mirror}/{rel}: {'缺失' if old is None else '内容与权威源不一致'}")
            if not check_only:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(payload)

        # 3) 清掉同步后留下的空目录
        if not check_only:
            for dirpath, dirnames, filenames in os.walk(mirror, topdown=False):
                if not dirnames and not filenames and dirpath != mirror:
                    os.rmdir(dirpath)

    return drift


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只报告漂移，不写文件")
    args = parser.parse_args()

    drift = sync(check_only=args.check)
    if not drift:
        print("镜像与 .agents/skills/synthetic-playtest/ 完全一致")
        return 0
    verb = "发现漂移" if args.check else "已同步"
    print(f"{verb}（{len(drift)} 项）：")
    for line in drift:
        print("  " + line)
    return 1 if args.check else 0


if __name__ == "__main__":
    sys.exit(main())

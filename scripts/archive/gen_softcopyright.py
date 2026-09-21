# -*- coding: utf-8 -*-
"""AudienceLens 软著登记 - 源程序鉴别材料生成脚本。

按《计算机软件著作权登记办法》第10条要求：
  源程序鉴别材料 = 源程序前、后各连续30页，每页不少于50行。

本脚本将项目主要源码按路径排序后拼接为单一逻辑流，
取前 1500 行（前30页×50行）与后 1500 行（后30页×50行），
按每页 50 行分页输出为文本文件。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 参与源程序鉴别的目录（按优先级排序）
SOURCE_DIRS = [
    "src",
    "web/backend/app",
    "web/frontend/src",
    "web/admin/src",
    "tools",
    "scripts",
]

EXCLUDE_PARTS = ("__pycache__", "node_modules", ".git", "dist", "build", "tests")

PAGE_LINES = 50
FRONT_PAGES = 30
BACK_PAGES = 30


def collect_files() -> list[Path]:
    files: list[Path] = []
    for rel in SOURCE_DIRS:
        base = ROOT / rel
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_dir():
                continue
            if any(part in p.parts for part in EXCLUDE_PARTS):
                continue
            if p.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".yaml", ".yml", ".json", ".html"}:
                files.append(p)
    return files


def read_lines(p: Path) -> list[str]:
    try:
        return p.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        try:
            return p.read_text(encoding="utf-8-sig").splitlines()
        except (UnicodeDecodeError, OSError):
            return []


def paginate(lines: list[str], page_lines: int) -> list[str]:
    """把行列表按固定行数分页，不足一页则补齐空行到整页。"""
    pages: list[str] = []
    total = len(lines)
    n_pages = (total + page_lines - 1) // page_lines
    for i in range(n_pages):
        chunk = lines[i * page_lines : (i + 1) * page_lines]
        chunk = chunk + [""] * (page_lines - len(chunk))
        pages.append(chunk)
    return pages


def main() -> int:
    files = collect_files()
    if not files:
        print("未找到任何源文件", file=sys.stderr)
        return 1

    all_lines: list[str] = []
    for f in files:
        all_lines.append(f"===== {f.relative_to(ROOT).as_posix()} =====")
        all_lines.extend(read_lines(f))

    print(f"参与文件数: {len(files)}，总行数: {len(all_lines)}")

    front = all_lines[: FRONT_PAGES * PAGE_LINES]
    back = all_lines[-BACK_PAGES * PAGE_LINES :]

    out_dir = ROOT / "软著登记材料"
    out_dir.mkdir(exist_ok=True)

    with (out_dir / "03-源程序鉴别材料-前30页.txt").open("w", encoding="utf-8") as fh:
        for i, page in enumerate(paginate(front, PAGE_LINES), 1):
            fh.write(f"=== 第{i}页 ===\n")
            fh.write("\n".join(page))
            fh.write("\n\n")

    with (out_dir / "04-源程序鉴别材料-后30页.txt").open("w", encoding="utf-8") as fh:
        for i, page in enumerate(paginate(back, PAGE_LINES), 1):
            fh.write(f"=== 第{i}页 ===\n")
            fh.write("\n".join(page))
            fh.write("\n\n")

    print(f"已生成: {out_dir / '03-源程序鉴别材料-前30页.txt'}")
    print(f"已生成: {out_dir / '04-源程序鉴别材料-后30页.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

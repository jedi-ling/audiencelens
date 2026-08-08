"""清掉 data/uploads/ 下没有数据库记录的孤儿文件。

背景：2025 年 7 月之前的 /api/uploads 会把上传的文本另存一份
data/uploads/{uuid}.txt，但从写下去那一刻起就没有任何代码读过它
（没有下载入口，stored_as 只存在于类型定义中）。后来写盘逻辑被删掉了，
留在盘上的文件却没人清——本机实测 141 个、205 KB，零数据库引用。

现在 uploaded_files 表接管了落盘，这个脚本负责两件事：
  1) 删掉那批历史遗留（库里根本没有对应记录）
  2) 日常兜底：删号时若某个文件删不掉（磁盘只读、被占用等），
     user_data_service 会跳过它以保证账号能删成功，残留由这里收走

默认只报告不删除，加 --apply 才真的动手。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import UploadedFile  # noqa: E402
from app.services import file_store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真的删除（默认只报告）")
    args = ap.parse_args()

    root = settings.upload_dir
    if not os.path.isdir(root):
        print(f"上传目录不存在，无需清理：{root}")
        return 0

    # uploaded_files 可能还没建（升级上来的实例第一次跑这个脚本时）。
    # create_all 只新增缺失的表，对已有表无副作用。
    init_db()

    db = SessionLocal()
    try:
        # 比对完整路径而不是文件名：分片目录下不同子目录可以有同名文件
        known = {
            os.path.normcase(os.path.abspath(file_store.storage_path(r.id, r.ext)))
            for r in db.query(UploadedFile).all()
        }
    finally:
        db.close()

    orphans = []
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.abspath(os.path.join(dirpath, name))
            if os.path.normcase(full) in known:
                continue
            # .part 是写盘中途的临时文件。正常流程会 os.replace 掉它，
            # 留下来的说明那次写入没跑完，同样是垃圾。
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            orphans.append(full)
            total += size

    print(f"上传目录：{root}")
    print(f"已登记文件：{len(known)} 个")
    print(f"孤儿文件：{len(orphans)} 个，合计 {total / 1024:.1f} KB")

    if not orphans:
        return 0
    if not args.apply:
        for f in orphans[:10]:
            print("  " + f)
        if len(orphans) > 10:
            print(f"  …还有 {len(orphans) - 10} 个")
        print("\n以上只是报告。确认无误后加 --apply 真正删除。")
        return 0

    removed = 0
    for f in orphans:
        try:
            os.remove(f)
            removed += 1
        except OSError as exc:
            print(f"  删除失败 {f}: {exc}")
    print(f"已删除 {removed}/{len(orphans)} 个，释放约 {total / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

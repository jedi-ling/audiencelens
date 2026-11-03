"""把 legacy 共享匿名桶（user_id = "anonymous" / 内容表里的 NULL）的存量行隔离起来。

背景与做法见 app/services/guest_service.py。一句话：游客身份 cookie
上线前，所有未登录访客共用 "anonymous"；这些行不属于任何人，改挂到一个
不对应任何账号的 owner 上，谁也看不到，但一行都不删。

默认只报告不改动，加 --apply 才真的改挂。可以重复跑（幂等）。

只在 AL_AUTH_ENABLED=true 的实例上有意义：单机开源形态（认证关闭）下
"anonymous" 就是这台机器的唯一使用者，隔离等于把本人的数据藏起来，
所以那种形态下必须显式 --force 才会执行。

用法（在 web/backend 目录下，读的是同一份 AL_* 配置）：
    python scripts/quarantine_anonymous.py            # 先看会动多少行
    python scripts/quarantine_anonymous.py --apply    # 真的改挂
Docker 部署：
    docker compose exec backend python scripts/quarantine_anonymous.py --apply
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.services import guest_service  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真的改挂（默认只报告）")
    ap.add_argument(
        "--force",
        action="store_true",
        help="AL_AUTH_ENABLED=false 时也执行（单机形态下通常不该这么做）",
    )
    args = ap.parse_args()

    if not settings.auth_enabled and not args.force:
        print(
            "AL_AUTH_ENABLED=false：单机形态下 anonymous 就是本机唯一的使用者，"
            "隔离会把你自己的数据藏起来。确实要做请加 --force。"
        )
        return 1

    init_db()
    db = SessionLocal()
    try:
        counts = guest_service.quarantine_legacy_anonymous(db, apply=args.apply)
    finally:
        db.close()

    total = sum(counts.values())
    for table, n in counts.items():
        print(f"  {table:24s} {n}")
    owner = guest_service.QUARANTINE_OWNER
    if args.apply:
        print(f"已把 {total} 行改挂到 {owner!r}（没有删除任何数据）。")
    else:
        print(f"共 {total} 行会被改挂到 {owner!r}。这是预览，加 --apply 才会执行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

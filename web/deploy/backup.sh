#!/usr/bin/env bash
# SQLite 在线备份（用 sqlite3 的 backup API，运行中也能安全备份，不是裸 cp）。
# 建议挂 cron：0 4 * * * /path/to/web/deploy/backup.sh >> /var/log/audiencelens-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."   # 进入 web/
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-7}"
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d-%H%M%S)
OUT="reviews-${STAMP}.db"

docker compose exec -T backend python - <<PY
import sqlite3
src = sqlite3.connect("/app/data/reviews.db")
dst = sqlite3.connect("/app/data/_backup_tmp.db")
src.backup(dst)
dst.close(); src.close()
print("backup ok")
PY

docker compose cp "backend:/app/data/_backup_tmp.db" "$BACKUP_DIR/$OUT"
docker compose exec -T backend rm -f /app/data/_backup_tmp.db
gzip "$BACKUP_DIR/$OUT"
echo "saved: $BACKUP_DIR/$OUT.gz"

# 只保留最近 KEEP 份
ls -1t "$BACKUP_DIR"/reviews-*.db.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

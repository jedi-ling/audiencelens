#!/usr/bin/env bash
# 数据库备份。备份哪种库、备份哪个文件，一律由后端进程实际使用的
# AL_DATABASE_URL 决定，不写死任何路径。
#
# 这个脚本以前无条件走 sqlite3 备份 /app/data/reviews.db，有两个致命后果：
#   1. 切到 PostgreSQL（DEPLOY.md 指定的生产库）后那个文件根本不存在，
#      sqlite3.connect() 会**当场建一个空库**再把空库备走，脚本照样 echo
#      "saved"、cron 日志天天报成功——等到真要恢复时才发现备份里什么都没有。
#   2. 就算是 SQLite，那个路径本身也是错的：容器里的库在
#      /app/web/backend/data/reviews.db（见 config.backend_dir），
#      /app/data/reviews.db 同样是被 connect() 现造出来的空文件。
# 备份最危险的失败模式不是"备份失败"，是"备份假装成功"。所以现在：
# 认得出的库按对应方式备份并校验产物大小，认不出就明确报错退出非零。
#
# 建议挂 cron（用 deploy/install-backup-cron.sh 安装，别只写在文档里）：
#   0 4 * * * /path/to/web/deploy/backup.sh >> /var/log/audiencelens-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."   # 进入 web/
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-7}"
# 产物小于这个字节数就当失败：空库 / 只有表头的 dump 都会落在这个量级以下，
# 而它们正是"看起来备份成功了"的典型形态。
MIN_BYTES="${MIN_BYTES:-1024}"
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d-%H%M%S)

# 唯一可信的事实源：后端进程自己算出来的 database_url（含 .env 与默认值），
# 而不是本机 shell 里恰好有没有导出过 AL_DATABASE_URL。
DB_URL=$(docker compose exec -T backend python -c \
    'from app.config import settings; print(settings.database_url)' | tr -d '\r')
if [ -z "$DB_URL" ]; then
    echo "ERROR: 取不到后端的 AL_DATABASE_URL（backend 容器没起来？），未做任何备份" >&2
    exit 1
fi
echo "database url: ${DB_URL%%://*}://…"   # 不打印口令

_verify_size() {
    # $1=文件路径。用 wc -c 而不是 stat：BSD/GNU 的 stat 参数不通用。
    # 太小的产物一律当失败并删掉——留着一个 200 字节的"备份"比没有备份更危险，
    # 它会让人以为自己有备份。
    local f="$1" size
    size=$(wc -c < "$f" | tr -d ' ')
    if [ "$size" -lt "$MIN_BYTES" ]; then
        echo "ERROR: 备份产物只有 ${size} 字节（阈值 ${MIN_BYTES}），几乎肯定是空库；已删除该文件" >&2
        rm -f "$f"
        exit 1
    fi
    echo "verified: $f (${size} bytes)"
}

case "$DB_URL" in
  sqlite*)
    # sqlite:///relative/path 与 sqlite:////abs/path 都由这一句还原
    DB_FILE="${DB_URL#sqlite:///}"
    OUT="$BACKUP_DIR/reviews-${STAMP}.db"
    TMP_IN_CONTAINER="${DB_FILE}.backup-tmp"

    # 用 sqlite3 的 backup API（运行中也能安全备份，不是裸 cp）。
    # 库文件不存在就直接失败——不能让 connect() 现造一个空库当备份。
    docker compose exec -T backend python - "$DB_FILE" "$TMP_IN_CONTAINER" <<'PY'
import os
import sqlite3
import sys

src_path, tmp_path = sys.argv[1], sys.argv[2]
if not os.path.isfile(src_path):
    sys.exit(f"ERROR: SQLite 库文件不存在：{src_path}（AL_DATABASE_URL 指错了？）")
src = sqlite3.connect(src_path)
dst = sqlite3.connect(tmp_path)
src.backup(dst)
tables = dst.execute(
    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
).fetchone()[0]
dst.close()
src.close()
if tables == 0:
    sys.exit(f"ERROR: 备份出来的库一张表都没有：{src_path} 是空库")
print(f"backup ok: {src_path} ({tables} tables)")
PY

    docker compose cp "backend:$TMP_IN_CONTAINER" "$OUT"
    docker compose exec -T backend rm -f "$TMP_IN_CONTAINER"
    # 先验未压缩的大小再压：一个只有表结构的 SQLite 也有 8KB 以上，
    # 压完却可能不到 1KB——拿压缩后的字节数当阈值会把新装实例误判成空库。
    _verify_size "$OUT"
    gzip -f "$OUT"
    echo "saved: $OUT.gz"
    ;;

  postgres://*|postgresql://*|postgresql+*://*)
    # SQLAlchemy 的 URL 带驱动后缀（postgresql+psycopg2://），libpq 不认，先剥掉
    PG_URL=$(printf '%s' "$DB_URL" | sed -E 's#^postgresql\+[A-Za-z0-9_]+://#postgresql://#')
    OUT="$BACKUP_DIR/reviews-${STAMP}.sql.gz"

    if command -v pg_dump >/dev/null 2>&1; then
        # set -o pipefail 已开：pg_dump 挂了整条管线就失败，不会留下半截 .gz
        pg_dump --no-owner --no-privileges --dbname="$PG_URL" | gzip > "$OUT"
    elif [ -n "${PG_DUMP_IMAGE:-}" ]; then
        # 宿主机没装 pg_dump 时的逃生舱：指定一个含 pg_dump 的镜像，例如
        #   PG_DUMP_IMAGE=postgres:16-alpine /path/to/backup.sh
        docker run --rm --network host -e PG_URL="$PG_URL" "$PG_DUMP_IMAGE" \
            sh -c 'pg_dump --no-owner --no-privileges --dbname="$PG_URL"' | gzip > "$OUT"
    else
        echo "ERROR: 库是 PostgreSQL，但本机既没有 pg_dump 也没设 PG_DUMP_IMAGE。" >&2
        echo "       未做任何备份（绝不假装成功）。装 postgresql-client，或设" >&2
        echo "       PG_DUMP_IMAGE=postgres:16-alpine 后重跑。" >&2
        exit 1
    fi
    # pg_dump 的产物是文本，压缩后仍远大于阈值；真备成空库时只有几百字节
    _verify_size "$OUT"
    echo "saved: $OUT"
    ;;

  *)
    echo "ERROR: 无法识别的 AL_DATABASE_URL 方言：${DB_URL%%://*}" >&2
    echo "       本脚本只会备份它确实认得的库；未做任何备份。" >&2
    exit 1
    ;;
esac

# 只保留最近 KEEP 份（两种产物各自计数：.db.gz 是 SQLite，.sql.gz 是 Postgres）。
# `|| true` 是必须的：两个 glob 里总有一个匹配不到文件，ls 会返回非零，
# 而 set -o pipefail 会把它变成整脚本失败——那就成了"备份明明成功却报错"，
# 同样是一种误导。清理失败不该改写备份本身的结论，但 rm 的报错照样进 stderr。
for pattern in "reviews-*.db.gz" "reviews-*.sql.gz"; do
    # shellcheck disable=SC2086
    ls -1t $BACKUP_DIR/$pattern 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f || true
done

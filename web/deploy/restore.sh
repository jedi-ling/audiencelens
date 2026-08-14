#!/usr/bin/env bash
# 从 backup.sh 的产物恢复数据库。与 backup.sh 严格对称：
# 备份哪种库由后端进程实际使用的 AL_DATABASE_URL 决定，恢复也一样。
#
# ── 为什么这个脚本必须存在 ────────────────────────────────────────────
# 没有恢复过的备份不算备份。backup.sh 已经很小心地防住了"备份假装成功"
# （空库检测、产物大小校验），但它防不住另一半：备份文件是好的，而**恢复
# 流程**从来没有人走通过——真出事那天才发现命令记不清、格式对不上、
# 或者恢复完少了半张表。那一刻是没有第二次机会的。
#
# ── 两个模式 ─────────────────────────────────────────────────────────
#   --drill        恢复到一个**临时库**，校验数据完整性后删掉。
#                  不碰生产库，安全到可以挂 cron 每周自动跑。
#                  这是本脚本的重点：恢复演练之所以没人做，是因为做它很吓人。
#                  把"吓人"这一层拿掉，演练才会真的发生。
#
#   --to-production 真恢复。会先把当前库另存一份（回滚用），再要求你手输
#                  确认词。绝不提供 --force / -y：这是不可逆操作，
#                  少打一次字省下的时间，远不值得误操作一次的代价。
#
# 用法：
#   web/deploy/restore.sh --drill                       # 演练最新一份备份
#   web/deploy/restore.sh --drill backups/reviews-X.gz  # 演练指定备份
#   web/deploy/restore.sh --to-production backups/reviews-X.gz
set -euo pipefail

cd "$(dirname "$0")/.."   # 进入 web/
BACKUP_DIR="${BACKUP_DIR:-./backups}"

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BACKEND_DIR="$REPO_ROOT/web/backend"

# venv 的 python 在 Linux 下是 bin/python，Windows（Git Bash / WSL 挂载）下是
# Scripts/python.exe。服务器只会命中前者，但开发机常是后者——而**演练必须能在
# 开发机上跑**，否则它只有在生产出事那天才第一次被执行，那正是本脚本要避免的。
_default_venv_py() {
    if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
        echo "$REPO_ROOT/.venv/bin/python"
    elif [ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
        echo "$REPO_ROOT/.venv/Scripts/python.exe"
    else
        echo "$REPO_ROOT/.venv/bin/python"   # 报错信息里显示这个路径
    fi
}
VENV_PY="${VENV_PY:-$(_default_venv_py)}"

MODE=""
BACKUP_FILE=""

usage() {
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-1}"
}

case "${1:-}" in
    --drill)         MODE="drill";      BACKUP_FILE="${2:-}" ;;
    --to-production) MODE="production"; BACKUP_FILE="${2:-}" ;;
    -h|--help)       usage 0 ;;
    *)
        echo "ERROR: 必须显式指定模式（--drill 或 --to-production）。" >&2
        echo "       不设默认模式是有意的：默认值一旦是 --to-production，" >&2
        echo "       一次手滑就会覆盖生产库；默认是 --drill 又会让人以为自己恢复了。" >&2
        echo >&2
        usage 1
        ;;
esac

# ---------------------------------------------------------------- 探测数据库

# 与 backup.sh 同一套探测逻辑：唯一可信的事实源是后端 config 自己算出来的
# database_url。两种部署形态（裸机 venv / Docker）都要能跑。
_probe_db_url() {
    local py="$1"
    "$py" -c 'from app.config import settings; print(settings.database_url)' 2>/dev/null | tr -d '\r'
}

DB_URL=""
if [ -x "$VENV_PY" ] && [ -d "$BACKEND_DIR" ]; then
    DB_URL=$(cd "$BACKEND_DIR" && _probe_db_url "$VENV_PY")
fi
if [ -z "$DB_URL" ] && command -v docker >/dev/null 2>&1; then
    DB_URL=$(docker compose exec -T backend python -c \
        'from app.config import settings; print(settings.database_url)' 2>/dev/null | tr -d '\r')
fi
if [ -z "$DB_URL" ]; then
    echo "ERROR: 取不到数据库地址，未做任何恢复。两条探测都失败了：" >&2
    echo "  · 本机 venv：$VENV_PY（不存在或 import app.config 失败）" >&2
    echo "  · Docker：docker compose exec backend（命令不存在或容器没起来）" >&2
    exit 1
fi
DIALECT="${DB_URL%%://*}"
echo "database url: ${DIALECT}://…"   # 不打印口令

# ---------------------------------------------------------------- 选备份文件

if [ -z "$BACKUP_FILE" ]; then
    # 没指定就取最新的一份。按库类型选对应后缀——拿 .sql.gz 去恢复 SQLite
    # 只会得到一个"恢复成功但库是空的"，正是本脚本要防的形态。
    case "$DIALECT" in
        sqlite*)                 PATTERN="reviews-*.db.gz" ;;
        postgres*|postgresql*)   PATTERN="reviews-*.sql.gz" ;;
        *) echo "ERROR: 无法识别的方言 $DIALECT" >&2; exit 1 ;;
    esac
    # shellcheck disable=SC2086
    BACKUP_FILE=$(ls -1t $BACKUP_DIR/$PATTERN 2>/dev/null | head -1 || true)
    if [ -z "$BACKUP_FILE" ]; then
        echo "ERROR: $BACKUP_DIR 下没有找到 $PATTERN 形式的备份。" >&2
        echo "       先跑一次 web/deploy/backup.sh，或用参数显式指定备份文件。" >&2
        exit 1
    fi
    echo "使用最新备份: $BACKUP_FILE"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: 备份文件不存在：$BACKUP_FILE" >&2
    exit 1
fi

# 后缀与库类型必须匹配。不检查的话，用 Postgres 的 .sql.gz 去"恢复" SQLite
# 会得到一个能跑完、但内容完全不对的结果。
case "$DIALECT:$BACKUP_FILE" in
    sqlite*:*.db.gz)                 ;;
    postgres*:*.sql.gz|postgresql*:*.sql.gz) ;;
    *)
        echo "ERROR: 备份文件类型与当前数据库对不上。" >&2
        echo "       当前库：$DIALECT   备份文件：$BACKUP_FILE" >&2
        echo "       SQLite 认 .db.gz，PostgreSQL 认 .sql.gz。" >&2
        exit 1
        ;;
esac

# ---------------------------------------------------------------- 完整性校验

# 恢复完必须回答"恢复出来的东西对不对"，而不只是"命令有没有报错"。
# 这里查两件事：核心表在不在、有没有行。空表不一定是错（新实例就是空的），
# 所以只在**全部**核心表都是 0 行时才报警——那才是"恢复了个空壳"的形态。
CORE_TABLES="users reviews judgments"

_verify_sqlite() {
    local db="$1"
    "${VERIFY_PY:-$VENV_PY}" - "$db" "$CORE_TABLES" <<'PY'
import sqlite3
import sys

db_path, core = sys.argv[1], sys.argv[2].split()
conn = sqlite3.connect(db_path)
existing = {
    r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
}
if not existing:
    sys.exit("ERROR: 恢复出来的库一张表都没有")

missing = [t for t in core if t not in existing]
if missing:
    sys.exit(f"ERROR: 恢复出来的库缺少核心表：{missing}（备份可能是坏的或来自别的库）")

counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in core}
conn.close()

print(f"  表总数: {len(existing)}")
for t, n in counts.items():
    print(f"  {t}: {n} 行")

# 全空才报警：新装实例本来就是空的，那不是恢复失败
if all(n == 0 for n in counts.values()):
    sys.exit(
        "ERROR: 核心表全部是 0 行。若这份备份来自一个已在使用的实例，"
        "说明备份内容是空的——请检查 backup.sh 的产物。"
    )
print("  完整性校验通过")
PY
}

# ---------------------------------------------------------------- 演练模式

if [ "$MODE" = "drill" ]; then
    echo
    echo "=== 恢复演练（不碰生产库）==="
    SCRATCH=$(mktemp -d)
    # 无论成功失败都清理：演练留下的临时库如果被人当成真库，就是新的事故源
    trap 'rm -rf "$SCRATCH"' EXIT

    case "$DIALECT" in
      sqlite*)
        gzip -dc "$BACKUP_FILE" > "$SCRATCH/restored.db"
        echo "已解压到临时库，开始校验："
        _verify_sqlite "$SCRATCH/restored.db"
        ;;
      postgres*|postgresql*)
        # 恢复到一个**临时数据库**而不是生产库。库名带时间戳避免撞车。
        PG_URL=$(printf '%s' "$DB_URL" | sed -E 's#^postgresql\+[A-Za-z0-9_]+://#postgresql://#')
        DRILL_DB="audiencelens_drill_$(date +%Y%m%d%H%M%S)"
        ADMIN_URL="${PG_URL%/*}/postgres"

        if ! command -v psql >/dev/null 2>&1; then
            echo "ERROR: 库是 PostgreSQL，但本机没有 psql，无法演练。" >&2
            echo "       装 postgresql-client 后重跑。" >&2
            exit 1
        fi
        echo "创建临时库 $DRILL_DB …"
        psql "$ADMIN_URL" -q -c "CREATE DATABASE $DRILL_DB;"
        # 无论后续成功失败都要删掉临时库，否则演练会在服务器上堆库
        trap 'psql "$ADMIN_URL" -q -c "DROP DATABASE IF EXISTS $DRILL_DB;" >/dev/null 2>&1; rm -rf "$SCRATCH"' EXIT

        gzip -dc "$BACKUP_FILE" | psql -q "${PG_URL%/*}/$DRILL_DB" >/dev/null
        echo "已恢复到临时库，开始校验："
        for t in $CORE_TABLES; do
            n=$(psql -tA "${PG_URL%/*}/$DRILL_DB" -c "SELECT COUNT(*) FROM $t;" 2>/dev/null || echo "MISSING")
            if [ "$n" = "MISSING" ]; then
                echo "ERROR: 恢复出来的库缺少核心表 $t（备份可能是坏的）" >&2
                exit 1
            fi
            echo "  $t: $n 行"
        done
        echo "  完整性校验通过"
        ;;
    esac

    echo
    echo "演练通过：$BACKUP_FILE 是一份可恢复的备份。"
    echo "临时库已清理，生产库未被触碰。"
    exit 0
fi

# ---------------------------------------------------------------- 真恢复

echo
echo "############################################################"
echo "#  即将用备份覆盖**生产数据库**"
echo "#    备份文件: $BACKUP_FILE"
echo "#    目标库:   ${DIALECT}://…"
echo "#  当前库里的数据会被完全替换。"
echo "############################################################"
echo

# 先给当前库另存一份。这不是可选步骤：恢复本身也可能选错文件，
# 没有这一份的话，一次误恢复就同时毁掉了"现在的数据"和"回滚的可能"。
echo "第 1 步：先备份当前库（回滚用）…"
if ! ./deploy/backup.sh; then
    echo "ERROR: 恢复前的安全备份失败，已中止。" >&2
    echo "       没有回滚点就恢复，等于把两次机会赌成一次。" >&2
    exit 1
fi

echo
echo "第 2 步：验证这份备份可恢复（先演练一遍）…"
"$0" --drill "$BACKUP_FILE"

echo
echo "第 3 步：确认。"
# 刻意要求手输完整词而不是 y/N：y 是肌肉记忆，RESTORE 不是。
printf '请输入 RESTORE 确认覆盖生产库（其它任何输入都会中止）: '
read -r CONFIRM
if [ "$CONFIRM" != "RESTORE" ]; then
    echo "已中止，未做任何改动。"
    exit 1
fi

echo
echo "第 4 步：恢复中…"
case "$DIALECT" in
  sqlite*)
    DB_FILE="${DB_URL#sqlite:///}"
    gzip -dc "$BACKUP_FILE" > "${DB_FILE}.restoring"
    # 先落到 .restoring 再原子改名：直接往 DB_FILE 写，中途失败会留下半个库
    mv "${DB_FILE}.restoring" "$DB_FILE"
    echo "已恢复，校验："
    _verify_sqlite "$DB_FILE"
    ;;
  postgres*|postgresql*)
    PG_URL=$(printf '%s' "$DB_URL" | sed -E 's#^postgresql\+[A-Za-z0-9_]+://#postgresql://#')
    gzip -dc "$BACKUP_FILE" | psql -q "$PG_URL"
    echo "已恢复，校验："
    for t in $CORE_TABLES; do
        n=$(psql -tA "$PG_URL" -c "SELECT COUNT(*) FROM $t;")
        echo "  $t: $n 行"
    done
    ;;
esac

echo
echo "恢复完成。请重启后端进程让连接池重新连接："
echo "  Docker:  docker compose restart backend"
echo "  裸机:    systemctl restart audiencelens-backend"

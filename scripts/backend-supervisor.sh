#!/usr/bin/env bash
# 开发用的后端看门狗：崩了自动拉起，输出统一进 logs/backend.log。
#
# 这不是部署入口。生产看 web/DEPLOY.md（Docker）或 web/DEPLOY-BAREMETAL.md
# （systemd），两者都有真正的进程管理器，不要把这个脚本搬进容器。
#
# 为什么在 scripts/ 而不是 logs/：脚本以前放在 logs/ 下，而 `/logs/` 整个
# 目录在 .gitignore 里——`git ls-files logs/` 是空的。也就是说 docs/MAINTENANCE.md
# 让读者敲的那行 `bash logs/backend-supervisor.sh`，在任何一个 fresh clone 上
# 都是 "No such file or directory"。脚本是源码，日志是产物，不该同住一个目录。
#
# 用法：
#   bash scripts/backend-supervisor.sh
#   PYTHON=py AL_PORT=8001 bash scripts/backend-supervisor.sh   # 覆盖默认值
set -u

# 仓库根：从脚本自身位置推出来，不写死任何机器专属路径
# （上一版写死了 C:/Users/Administrator/... 与 C:/pilotos/python/python.exe，
#  换一台机器、甚至换一个用户名就跑不起来）。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

PYTHON="${PYTHON:-python}"
AL_HOST="${AL_HOST:-127.0.0.1}"
# 8001 与 web/frontend 的 vite 代理目标一致，改这里记得同步改 vite.config.ts
AL_PORT="${AL_PORT:-8001}"
RESTART_DELAY="${RESTART_DELAY:-2}"

# 认证默认开：关掉时所有访客共用一个 anonymous 身份、互相看得见，
# 那是本地单人自用才可接受的形态，不该是随手起服务时的默认。
export AL_AUTH_ENABLED="${AL_AUTH_ENABLED:-true}"

LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/backend.log"

cd "$REPO_ROOT/web/backend" || exit 1

echo "[supervisor] repo=$REPO_ROOT python=$PYTHON listening on $AL_HOST:$AL_PORT" | tee -a "$LOG"

while true; do
  echo "[supervisor] $(date '+%Y-%m-%d %H:%M:%S') starting uvicorn" >> "$LOG"
  "$PYTHON" -m uvicorn app.main:app --host "$AL_HOST" --port "$AL_PORT" >> "$LOG" 2>&1
  code=$?
  # 128+2 = Ctrl-C。手动中断时不要自动拉起，否则退不出去。
  if [ "$code" -eq 130 ]; then
    echo "[supervisor] $(date '+%Y-%m-%d %H:%M:%S') interrupted, exiting" >> "$LOG"
    exit 0
  fi
  echo "[supervisor] $(date '+%Y-%m-%d %H:%M:%S') uvicorn exited with code $code — restarting in ${RESTART_DELAY}s" >> "$LOG"
  sleep "$RESTART_DELAY"
done

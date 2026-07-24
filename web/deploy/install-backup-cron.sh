#!/usr/bin/env bash
# 把 backup.sh 真正装进 crontab——此前只在 backup.sh 顶部注释和 DEPLOY.md 里
# "建议挂 cron"，没有任何东西实际执行这一步：漏做的话备份就是纸面上的，
# 数据库单点无备份。幂等：重复运行不会叠加出第二条同样的 crontab 行。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SH="$SCRIPT_DIR/backup.sh"
SCHEDULE="${BACKUP_CRON_SCHEDULE:-0 4 * * *}"   # 默认每天 04:00
LOG_FILE="${BACKUP_LOG_FILE:-/var/log/audiencelens-backup.log}"

if [[ ! -f "$BACKUP_SH" ]]; then
    echo "找不到 $BACKUP_SH" >&2
    exit 1
fi
chmod +x "$BACKUP_SH"

CRON_LINE="$SCHEDULE cd $SCRIPT_DIR/.. && $BACKUP_SH >> $LOG_FILE 2>&1"
MARKER="# audiencelens-backup"  # 用于识别/替换本脚本安装的行，不影响用户自己的其他 crontab 内容

EXISTING="$(crontab -l 2>/dev/null || true)"
if echo "$EXISTING" | grep -qF "$MARKER"; then
    # 已装过：替换成本次的 schedule/路径（用户可能改了 BACKUP_CRON_SCHEDULE 重新执行本脚本）
    NEW="$(echo "$EXISTING" | grep -vF "$MARKER")"
    printf '%s\n%s %s\n' "$NEW" "$CRON_LINE" "$MARKER" | crontab -
    echo "已更新 crontab 备份任务：$SCHEDULE"
else
    printf '%s\n%s %s\n' "$EXISTING" "$CRON_LINE" "$MARKER" | crontab -
    echo "已安装 crontab 备份任务：$SCHEDULE"
fi

crontab -l | grep -F "$MARKER"
echo "备份日志：$LOG_FILE"
echo "验证：手动跑一次 $BACKUP_SH 确认能成功备份后再放心等 cron 触发。"

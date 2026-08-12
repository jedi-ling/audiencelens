#!/usr/bin/env bash
# 把 backup.sh 与 restore.sh --drill 真正装进 crontab——此前只在脚本顶部注释和
# DEPLOY.md 里"建议挂 cron"，没有任何东西实际执行这一步：漏做的话备份就是纸面上的，
# 数据库单点无备份。幂等：重复运行不会叠加出第二条同样的 crontab 行。
#
# 装两条而不是一条：
#   · 每天备份
#   · 每周演练一次恢复（restore.sh --drill，恢复到临时库校验后删掉，不碰生产）
#
# 为什么演练也要挂 cron：没有恢复过的备份不算备份。backup.sh 能防住"备份产物是
# 空的"，防不住"恢复流程从来没人走通过"——真出事那天才发现命令记不清、
# 格式对不上。演练如果只写在文档里，三个月后就没人记得跑了。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SH="$SCRIPT_DIR/backup.sh"
RESTORE_SH="$SCRIPT_DIR/restore.sh"
SCHEDULE="${BACKUP_CRON_SCHEDULE:-0 4 * * *}"          # 默认每天 04:00
DRILL_SCHEDULE="${DRILL_CRON_SCHEDULE:-30 4 * * 1}"    # 默认每周一 04:30（备份之后）
LOG_FILE="${BACKUP_LOG_FILE:-/var/log/audiencelens-backup.log}"
DRILL_LOG_FILE="${DRILL_LOG_FILE:-/var/log/audiencelens-restore-drill.log}"

if [[ ! -f "$BACKUP_SH" ]]; then
    echo "找不到 $BACKUP_SH" >&2
    exit 1
fi
chmod +x "$BACKUP_SH"
[[ -f "$RESTORE_SH" ]] && chmod +x "$RESTORE_SH"

# 用于识别/替换本脚本安装的行，不影响用户自己的其他 crontab 内容
BACKUP_MARKER="# audiencelens-backup"
DRILL_MARKER="# audiencelens-restore-drill"

CRON_LINE="$SCHEDULE cd $SCRIPT_DIR/.. && $BACKUP_SH >> $LOG_FILE 2>&1"
DRILL_LINE="$DRILL_SCHEDULE cd $SCRIPT_DIR/.. && $RESTORE_SH --drill >> $DRILL_LOG_FILE 2>&1"

# 先把本脚本装过的两行都摘掉，再统一append 回去。分别 grep -v 两个 marker
# 是必须的：只摘一个的话，改了 schedule 重跑会留下旧的那条，变成一天备份两次。
EXISTING="$(crontab -l 2>/dev/null || true)"
CLEANED="$(printf '%s\n' "$EXISTING" | grep -vF "$BACKUP_MARKER" | grep -vF "$DRILL_MARKER" || true)"

printf '%s\n%s %s\n%s %s\n' \
    "$CLEANED" \
    "$CRON_LINE" "$BACKUP_MARKER" \
    "$DRILL_LINE" "$DRILL_MARKER" \
    | crontab -

echo "已安装/更新 crontab："
crontab -l | grep -F -e "$BACKUP_MARKER" -e "$DRILL_MARKER"
echo
echo "备份日志：    $LOG_FILE       （每天 $SCHEDULE）"
echo "演练日志：    $DRILL_LOG_FILE （每周 $DRILL_SCHEDULE）"
echo
echo "现在先手动各跑一次确认能通过，再放心等 cron 触发："
echo "  $BACKUP_SH"
echo "  $RESTORE_SH --drill"
echo
echo "⚠ 演练失败时 cron 只会写进日志，不会主动通知你。"
echo "  接了监控之后，建议把 $DRILL_LOG_FILE 里的非零退出也纳入告警。"

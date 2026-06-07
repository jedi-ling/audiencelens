#!/bin/bash
# log-agent.sh — SubagentStart hook for AudienceLens synthetic-playtest
# Logs persona agent invocations to production/session-state/agent-audit.log
# Format: timestamp, agent_name, task_type
# Creates directory if not exists
# Advisory only — always exits 0

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$PROJECT_DIR/production/session-state"
LOG_FILE="$LOG_DIR/agent-audit.log"

if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR" 2>/dev/null
fi

AGENT_NAME="${1:-unknown}"
TASK_TYPE="${2:-synthetic-review}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S")

echo "$TIMESTAMP, $AGENT_NAME, $TASK_TYPE" >> "$LOG_FILE" 2>/dev/null

exit 0

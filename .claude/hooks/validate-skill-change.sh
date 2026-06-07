#!/bin/bash
# validate-skill-change.sh — PostToolUse (Write/Edit) hook for AudienceLens synthetic-playtest
# Only fires when editing files in .claude/skills/synthetic-playtest/
# Prints advisory reminder to test after skill file changes
# Advisory only — always exits 0

TOOL_NAME="$1"
FILE_PATH="$2"

if [ "$TOOL_NAME" != "Write" ] && [ "$TOOL_NAME" != "Edit" ]; then
    exit 0
fi

case "$FILE_PATH" in
    */.claude/skills/synthetic-playtest/*)
        echo "[AudienceLens] Skill file changed — consider testing with a quick review run" >&2
        ;;
esac

exit 0

#!/bin/bash
# session-start.sh — Session open hook for AudienceLens synthetic-playtest
# Shows current project info, checks for persona files in .claude/agents/
# Suggests running /synthetic-playtest if no prior reports exist
# Advisory only — always exits 0

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
AGENTS_DIR="$PROJECT_DIR/.claude/agents"

echo "[AudienceLens] Session started — project: $(basename "$PROJECT_DIR")" >&2

if [ -d "$AGENTS_DIR" ]; then
    PERSONA_COUNT=$(find "$AGENTS_DIR" -maxdepth 1 -name "*.yaml" -o -name "*.yml" -o -name "*.md" 2>/dev/null | wc -l)
    if [ "$PERSONA_COUNT" -gt 0 ]; then
        echo "[AudienceLens] Found $PERSONA_COUNT persona file(s) in .claude/agents/" >&2
    else
        echo "[AudienceLens] No persona files found in .claude/agents/" >&2
    fi
else
    echo "[AudienceLens] .claude/agents/ directory does not exist yet" >&2
fi

REPORT_COUNT=$(find "$PROJECT_DIR" -maxdepth 3 -name "*audiencelens-report*" 2>/dev/null | wc -l)
if [ "$REPORT_COUNT" -eq 0 ]; then
    echo "[AudienceLens] No prior reports found — consider running /synthetic-playtest to generate one" >&2
else
    echo "[AudienceLens] Found $REPORT_COUNT prior report(s)" >&2
fi

exit 0

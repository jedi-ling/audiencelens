#!/bin/bash
# validate-report.sh — PreToolUse (Write) hook for AudienceLens synthetic-playtest
# Only fires when writing files matching *audiencelens-report*
# Validates JSON reports have required top-level keys and HTML reports contain synthetic banner
# Advisory only — always exits 0, never blocks operations

TOOL_NAME="$1"
FILE_PATH="$2"

if [ "$TOOL_NAME" != "Write" ]; then
    exit 0
fi

case "$FILE_PATH" in
    *audiencelens-report*)
        ;;
    *)
        exit 0
        ;;
esac

if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

case "$FILE_PATH" in
    *.json)
        REQUIRED_KEYS="meta executive_summary consensus persona_notes"
        MISSING=""
        for key in $REQUIRED_KEYS; do
            if ! grep -qE "\"$key\"" "$FILE_PATH"; then
                MISSING="$MISSING $key"
            fi
        done
        if [ -n "$MISSING" ]; then
            echo "[AudienceLens] Advisory: JSON report missing top-level keys:$MISSING" >&2
        else
            echo "[AudienceLens] JSON report validation passed — all required keys present" >&2
        fi
        ;;
    *.html)
        if ! grep -qE "Synthetic Playtest|synthetic-playtest|AudienceLens" "$FILE_PATH"; then
            echo "[AudienceLens] Advisory: HTML report missing synthetic banner text" >&2
        else
            echo "[AudienceLens] HTML report validation passed — synthetic banner found" >&2
        fi
        ;;
esac

exit 0

#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/hexwatch_v6"
MONO="$ROOT/hexwatch_v6_monolith.py"
LOGS="$ROOT/logs"
RUN="$ROOT/run"
mkdir -p "$LOGS" "$RUN"

pkill -f "$MONO" 2>/dev/null || true
sleep 1

python3 -m py_compile "$MONO"
nohup python3 "$MONO" >> "$LOGS/nohup.log" 2>&1 &
sleep 2
pgrep -af hexwatch_v6_monolith || pgrep -af "$MONO" || true

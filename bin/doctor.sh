#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/hexwatch_v6"
MONO="$ROOT/hexwatch_v6_monolith.py"
BIN="$ROOT/bin"
LOGS="$ROOT/logs"
REPORTS="$ROOT/reports"
STATE="$ROOT/state"

echo "=== doctor: compile ==="
python3 -m py_compile "$MONO"

echo
echo "=== doctor: process ==="
pgrep -af hexwatch_v6_monolith || true

echo
echo "=== doctor: autonomy state ==="
sed -n '1,200p' "$STATE/autonomy.json" 2>/dev/null || true

echo
echo "=== doctor: goal ==="
sed -n '1,50p' "$STATE/goal.txt" 2>/dev/null || true

echo
echo "=== doctor: logs ==="
tail -n 50 "$LOGS/main.log" 2>/dev/null || true
echo
tail -n 50 "$LOGS/error.log" 2>/dev/null || true

echo
echo "=== doctor: talk ping ==="
"$BIN/talk.sh" ping || true

#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/hexwatch_v6"
MONO="$ROOT/hexwatch_v6_monolith.py"
LOGS="$ROOT/logs"
REPORTS="$ROOT/reports"
RUN="$ROOT/run"

echo "[hexwatch_v6 health]"
echo "ts: $(date --iso-8601=seconds)"
echo "root: $ROOT"
echo
echo "-- process --"
pgrep -af hexwatch_v6_monolith || true
echo
echo "-- compile --"
python3 -m py_compile "$MONO" && echo "compile_ok" || echo "compile_failed"
echo
echo "-- main log tail --"
tail -n 40 "$LOGS/main.log" 2>/dev/null || true
echo
echo "-- error log tail --"
tail -n 40 "$LOGS/error.log" 2>/dev/null || true
echo
echo "-- status report --"
sed -n '1,200p' "$REPORTS/status.txt" 2>/dev/null || true
echo
echo "-- rollup report --"
sed -n '1,120p' "$REPORTS/rollup.txt" 2>/dev/null || true
echo
echo "-- run dir --"
ls -lah "$RUN" 2>/dev/null || true

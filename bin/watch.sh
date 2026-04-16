#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"
STATUS="$ROOT/reports/status.txt"
DAILY="$ROOT/reports/daily.txt"
AUDIT="$ROOT/logs/audit.log"
ERRORS="$ROOT/logs/error.log"
METRICS="$ROOT/state/metrics.json"
MEMORY="$ROOT/state/memory.json"
GOAL="$ROOT/state/goal.txt"

while true; do
  clear
  echo "=== HEXWATCH V6 OPERATOR DASHBOARD ==="
  echo "ts: $(date --iso-8601=seconds)"
  echo

  echo "--- goal ---"
  sed -n '1,5p' "$GOAL" 2>/dev/null || echo "(no goal)"
  echo

  echo "--- status ---"
  sed -n '1,20p' "$STATUS" 2>/dev/null || echo "(no status)"
  echo

  echo "--- metrics ---"
  sed -n '1,40p' "$METRICS" 2>/dev/null || echo "(no metrics)"
  echo

  echo "--- memory ---"
  sed -n '1,40p' "$MEMORY" 2>/dev/null || echo "{}"
  echo

  echo "--- daily report ---"
  sed -n '1,20p' "$DAILY" 2>/dev/null || echo "(no daily report)"
  echo

  echo "--- audit tail ---"
  tail -n 15 "$AUDIT" 2>/dev/null || echo "(no audit log)"
  echo

  echo "--- error tail ---"
  tail -n 10 "$ERRORS" 2>/dev/null || echo "(no errors)"
  echo

  echo "[ctrl+c to exit]"
  sleep 3
done

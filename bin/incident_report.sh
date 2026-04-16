#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"
REPORT="$ROOT/reports/incidents.txt"
AUDIT="$ROOT/logs/audit.log"
ERRORS="$ROOT/logs/error.log"
STATUS="$ROOT/reports/status.txt"
METRICS="$ROOT/state/metrics.json"

{
  echo "HEXWATCH INCIDENT REPORT"
  echo "ts: $(date --iso-8601=seconds)"
  echo
  echo "--- status ---"
  sed -n '1,20p' "$STATUS" 2>/dev/null || true
  echo
  echo "--- metrics ---"
  sed -n '1,40p' "$METRICS" 2>/dev/null || true
  echo
  echo "--- recent audit ---"
  tail -n 25 "$AUDIT" 2>/dev/null || true
  echo
  echo "--- recent errors ---"
  tail -n 25 "$ERRORS" 2>/dev/null || true
} > "$REPORT"

echo "$REPORT"

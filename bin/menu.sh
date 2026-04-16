#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"

cat <<'TXT'
HEXWATCH V6 MENU

1) launch
2) stop
3) status
4) metrics
5) report anomaly
6) watch dashboard
7) backup
8) incident report
TXT

read -rp "choice> " choice

case "$choice" in
  1) "$ROOT/bin/launch.sh" ;;
  2) "$ROOT/bin/stop.sh" ;;
  3) "$ROOT/bin/talk.sh" status ;;
  4) "$ROOT/bin/talk.sh" metrics ;;
  5) "$ROOT/bin/talk.sh" "report anomaly" ;;
  6) "$ROOT/bin/watch.sh" ;;
  7) "$ROOT/bin/backup.sh" ;;
  8) "$ROOT/bin/incident_report.sh" ;;
  *) echo "unknown choice" ;;
esac

#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"
MONO="$ROOT/hexwatch_v6_monolith.py"
RUN="$ROOT/run"
LOGS="$ROOT/logs"
LOCKFILE="$RUN/monolith.lock"

mkdir -p "$RUN" "$LOGS"

echo "[launch] compile check"
python3 -m py_compile "$MONO"

echo "[launch] stopping old process if present"
pkill -f "$MONO" 2>/dev/null || true
sleep 1

if [[ -f "$LOCKFILE" ]]; then
  old_pid="$(cat "$LOCKFILE" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" ]]; then
    if kill -0 "$old_pid" 2>/dev/null; then
      echo "[launch] live pid still owns lock: $old_pid"
      exit 1
    else
      echo "[launch] removing stale lock"
      rm -f "$LOCKFILE"
    fi
  else
    echo "[launch] removing unreadable lock"
    rm -f "$LOCKFILE"
  fi
fi

echo "[launch] starting daemon"
nohup python3 "$MONO" >> "$LOGS/nohup.log" 2>&1 &
sleep 3

echo "[launch] process:"
pgrep -af hexwatch_v6_monolith || pgrep -af "$MONO" || true

echo
echo "[launch] quick status:"
"$ROOT/bin/talk.sh" status || true

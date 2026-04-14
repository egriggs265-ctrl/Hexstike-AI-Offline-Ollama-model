#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"
INBOX="$ROOT/run/chat.inbox"
OUTBOX="$ROOT/run/chat.outbox"
LAST="$ROOT/reports/last_reply.txt"

mkdir -p "$ROOT/run" "$ROOT/reports"
touch "$INBOX" "$OUTBOX" "$LAST"

msg="${*:-}"
if [[ -z "$msg" ]]; then
  echo 'usage: ~/hexwatch_v6/bin/talk.sh "ping|status|rollup|ask ...|note ...|goal ...|autonomy on|autonomy off"'
  exit 1
fi

ts="$(date +%s)"
marker="__TALK_MARKER_${ts}_$$__"

{
  printf '%s\n' "$marker"
  printf '%s\n' "$msg"
} >> "$INBOX"

echo "[sent] $msg"

if [[ "$msg" == "ping" ]]; then
  for _ in $(seq 1 20); do
    if grep -q 'pong' "$OUTBOX" 2>/dev/null; then
      tail -n 5 "$OUTBOX"
      exit 0
    fi
    sleep 1
  done
  echo "[no pong yet]"
  exit 0
fi

for _ in $(seq 1 90); do
  if [[ -s "$LAST" ]]; then
    if ! grep -q "$marker" "$LAST" 2>/dev/null; then
      sed -n '1,240p' "$LAST"
      exit 0
    fi
  fi
  sleep 2
done

echo "[no new reply yet]"
exit 0

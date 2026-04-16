#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"
INBOX="$ROOT/run/chat.inbox"
OUTBOX="$ROOT/run/chat.outbox"

mkdir -p "$ROOT/run"
touch "$INBOX" "$OUTBOX"

msg="${*:-}"
if [[ -z "$msg" ]]; then
  echo "usage: talk.sh 'ping|status|metrics|tail audit|ask ...'"
  exit 1
fi

before_bytes="$(wc -c < "$OUTBOX" 2>/dev/null || echo 0)"

printf '%s\n' "$msg" >> "$INBOX"
echo "[sent] $msg"

for _ in $(seq 1 60); do
  now_bytes="$(wc -c < "$OUTBOX" 2>/dev/null || echo 0)"
  if [[ "$now_bytes" -gt "$before_bytes" ]]; then
    python3 - "$OUTBOX" "$before_bytes" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
offset = int(sys.argv[2])
data = path.read_text(encoding="utf-8")
print(data[offset:].lstrip("\n"), end="")
PY
    exit 0
  fi
  sleep 1
done

echo "[no new reply yet]"

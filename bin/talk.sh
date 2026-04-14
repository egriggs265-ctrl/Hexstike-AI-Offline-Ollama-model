            #!/usr/bin/env bash
            set -euo pipefail
            ROOT="${HOME}/hexwatch_v6"
            OUT="$ROOT/run/chat.outbox"
            IN="$ROOT/run/chat.inbox"
            MSG="${*:-status}"

            mkdir -p "$ROOT/run"
            touch "$OUT" "$IN"

            before=$(wc -l < "$OUT" 2>/dev/null || echo 0)
            printf '%s
' "$MSG" >> "$IN"
            echo "[sent] $MSG"
            sleep 2
            after=$(wc -l < "$OUT" 2>/dev/null || echo 0)

            if [ "$after" -gt "$before" ]; then
              sed -n "$((before+1)),$((after))p" "$OUT"
            else
              echo "[no new reply yet]"
            fi

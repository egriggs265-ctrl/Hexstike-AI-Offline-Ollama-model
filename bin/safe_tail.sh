#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/hexwatch_v6"
target="${1:-logs/main.log}"
lines="${2:-80}"

case "$target" in
  logs/main.log|logs/error.log|logs/chat_history.log|reports/status.txt|reports/rollup.txt|reports/last_reply.txt)
    tail -n "$lines" "$ROOT/$target"
    ;;
  *)
    echo "blocked: $target"
    exit 2
    ;;
esac

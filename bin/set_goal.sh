#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/hexwatch_v6"
STATE="$ROOT/state"
mkdir -p "$STATE"
printf '%s\n' "$*" > "$STATE/goal.txt"
echo "[goal set]"
cat "$STATE/goal.txt"

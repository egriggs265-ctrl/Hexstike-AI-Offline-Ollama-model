#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"
MONO="$ROOT/hexwatch_v6_monolith.py"
LOCKFILE="$ROOT/run/monolith.lock"

pkill -f "$MONO" 2>/dev/null || true
sleep 1
rm -f "$LOCKFILE"
echo "[stop] stopped"

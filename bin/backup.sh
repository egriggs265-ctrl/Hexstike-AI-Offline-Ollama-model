#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/hexwatch_v6"
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="$ROOT/tmp/backup_$STAMP"

mkdir -p "$DEST"

cp -a "$ROOT/hexwatch_v6_monolith.py" "$DEST/" 2>/dev/null || true
cp -a "$ROOT/bin" "$DEST/" 2>/dev/null || true
cp -a "$ROOT/run" "$DEST/" 2>/dev/null || true
cp -a "$ROOT/logs" "$DEST/" 2>/dev/null || true
cp -a "$ROOT/state" "$DEST/" 2>/dev/null || true
cp -a "$ROOT/reports" "$DEST/" 2>/dev/null || true

echo "$DEST"

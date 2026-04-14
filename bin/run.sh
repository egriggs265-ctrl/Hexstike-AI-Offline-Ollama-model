#!/usr/bin/env bash
set -euo pipefail
ROOT="${HOME}/hexwatch_v6"
exec python3 "$ROOT/hexwatch_v6_monolith.py" --root "$ROOT" --foreground

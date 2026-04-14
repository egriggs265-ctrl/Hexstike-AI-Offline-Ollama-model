#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/hexwatch_v6"
STATE="$ROOT/state"
mkdir -p "$STATE"
mode="${1:-status}"

python3 - "$STATE/autonomy.json" "$mode" <<'PY'
import json, sys, pathlib
path = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
data = {
    "enabled": False,
    "interval_seconds": 90,
    "cooldown_seconds": 60,
    "max_reply_chars": 900,
    "allowed_actions": ["reply", "status", "rollup", "note", "tail"],
    "operator_only_shell": True,
    "tail_allowlist": [
        "logs/main.log",
        "logs/error.log",
        "logs/chat_history.log",
        "reports/status.txt",
        "reports/rollup.txt",
        "reports/last_reply.txt"
    ]
}
if path.exists():
    try:
        data.update(json.loads(path.read_text()))
    except Exception:
        pass

if mode == "on":
    data["enabled"] = True
elif mode == "off":
    data["enabled"] = False
elif mode.startswith("interval="):
    data["interval_seconds"] = int(mode.split("=",1)[1])

path.write_text(json.dumps(data, indent=2) + "\n")
print(json.dumps(data, indent=2))
PY

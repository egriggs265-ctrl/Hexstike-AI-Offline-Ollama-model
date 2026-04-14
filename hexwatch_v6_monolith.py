#!/usr/bin/env python3
import os, sys, time, json, subprocess
from pathlib import Path

ROOT = Path.home() / "hexwatch_v6"
INBOX = ROOT / "run/chat.inbox"
OUTBOX = ROOT / "run/chat.outbox"
LOG = ROOT / "logs/main.log"

MODEL = os.environ.get("HEXWATCH_MODEL", "phi3:mini")

def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")

def write_out(msg):
    with open(OUTBOX, "a") as f:
        f.write(msg + "\n")

def ai_reply(prompt):
    try:
        r = subprocess.run(
            ["ollama", "run", MODEL],
            input=prompt,
            text=True,
            capture_output=True
        )
        return (r.stdout or "").strip() or "(no response)"
    except Exception as e:
        return f"AI error: {e}"

def handle(cmd):
    if cmd == "ping":
        return f"pong {time.time()}"
    if cmd == "status":
        return "hexwatch v6 alive"
    if cmd.startswith("ask "):
        return ai_reply(cmd[4:])
    return f"unknown command: {cmd}"

def main():
    log("started")

    last_size = 0

    while True:
        if INBOX.exists():
            data = INBOX.read_text()
            if len(data) > last_size:
                new = data[last_size:].strip().splitlines()
                last_size = len(data)

                for line in new:
                    out = handle(line.strip())
                    write_out(out)
                    log(f"IN: {line} | OUT: {out}")

        time.sleep(1)

if __name__ == "__main__":
    main()

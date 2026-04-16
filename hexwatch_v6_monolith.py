#!/usr/bin/env python3
import os
import time
import json
import atexit
import subprocess
from pathlib import Path

ROOT = Path.home() / "hexwatch_v6"
RUN = ROOT / "run"
LOGS = ROOT / "logs"
STATE = ROOT / "state"
REPORTS = ROOT / "reports"
TMP = ROOT / "tmp"

INBOX = RUN / "chat.inbox"
OUTBOX = RUN / "chat.outbox"
MAIN_LOG = LOGS / "main.log"
ERROR_LOG = LOGS / "error.log"
AUDIT_LOG = LOGS / "audit.log"
LOCKFILE = RUN / "monolith.lock"

MODEL = os.environ.get("HEXWATCH_MODEL", "phi3:mini")
FALLBACK_MODEL = os.environ.get("HEXWATCH_FALLBACK_MODEL", "")

AUTONOMY_BACKOFF = {
    "fail_count": 0,
    "last_fail": 0
}

def autonomy_should_run():
    if AUTONOMY_BACKOFF["fail_count"] >= 3:
        if time.time() - AUTONOMY_BACKOFF["last_fail"] < 30:
            return False
    return True

AUTONOMY_STATE = {"last_tick": 0.0, "last_ai_tick": 0.0}


def ensure_dirs() -> None:
    for p in (RUN, LOGS, STATE, REPORTS, TMP):
        p.mkdir(parents=True, exist_ok=True)
    INBOX.touch(exist_ok=True)
    OUTBOX.touch(exist_ok=True)


def log(msg: str) -> None:
    with open(MAIN_LOG, "a", encoding="utf-8") as f:
        f.write(msg.rstrip("\n") + "\n")


def log_error(msg: str) -> None:
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(msg.rstrip("\n") + "\n")


def audit(msg: str) -> None:
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.time()} | {msg.rstrip()}\n")


def write_out(msg: str) -> None:
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(msg.rstrip("\n") + "\n")


def tail_file(path: Path, n: int = 20) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[-n:]) if lines else "(empty)"
    except Exception as e:
        return f"tail error: {e}"



def safe_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

def one_line(text: str, limit: int = 260) -> str:
    text = " ".join(str(text).split())
    return text[:limit].strip()

def anomaly_snapshot() -> dict:
    audit_tail = tail_file(AUDIT_LOG, 40)
    error_tail = tail_file(ERROR_LOG, 20)

    score = 0
    reasons = []

    auto_skip_count = audit_tail.count("AUTO_SKIP")
    if auto_skip_count >= 5:
        score += 1
        reasons.append(f"many_auto_skips={auto_skip_count}")

    if "loop error:" in error_tail:
        score += 3
        reasons.append("loop_error_seen")

    if "ERROR heartbeat loop failure" in error_tail:
        score += 1
        reasons.append("legacy_heartbeat_errors_present")

    if "AUTO_REPLY:" in audit_tail:
        score += 1
        reasons.append("autonomy_reply_activity")

    return {
        "score": score,
        "reasons": reasons,
        "audit_tail": audit_tail,
        "error_tail": error_tail,
    }


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_memory() -> dict:
    data = read_json(STATE / "memory.json", {})
    return data if isinstance(data, dict) else {}


def save_memory(mem: dict) -> None:
    write_json(STATE / "memory.json", mem)


def load_metrics() -> dict:
    data = read_json(
        STATE / "metrics.json",
        {
            "commands": 0,
            "ai_calls": 0,
            "errors": 0,
            "autonomy_ticks": 0,
            "started_at": time.time(),
            "last_command": "",
            "last_error": "",
        },
    )
    if not isinstance(data, dict):
        data = {}
    data.setdefault("commands", 0)
    data.setdefault("ai_calls", 0)
    data.setdefault("errors", 0)
    data.setdefault("autonomy_ticks", 0)
    data.setdefault("started_at", time.time())
    data.setdefault("last_command", "")
    data.setdefault("last_error", "")
    return data


def save_metrics(m: dict) -> None:
    write_json(STATE / "metrics.json", m)


def bump_metric(name: str, amount: int = 1) -> None:
    m = load_metrics()
    m[name] = int(m.get(name, 0)) + amount
    save_metrics(m)


def set_last_command(cmd: str) -> None:
    m = load_metrics()
    m["last_command"] = cmd
    save_metrics(m)


def set_last_error(err: str) -> None:
    m = load_metrics()
    m["last_error"] = err
    m["errors"] = int(m.get("errors", 0)) + 1
    save_metrics(m)


def load_autonomy_config() -> dict:
    data = read_json(
        STATE / "autonomy.json",
        {
            "enabled": False,
            "interval_seconds": 60,
            "max_note_chars": 220,
            "max_reply_chars": 260,
            "min_ai_interval_seconds": 20,
        },
    )
    if not isinstance(data, dict):
        data = {}
    return {
        "enabled": bool(data.get("enabled", False)),
        "interval_seconds": max(15, int(data.get("interval_seconds", 60))),
        "max_note_chars": max(80, int(data.get("max_note_chars", 220))),
        "max_reply_chars": max(80, int(data.get("max_reply_chars", 260))),
        "min_ai_interval_seconds": max(5, int(data.get("min_ai_interval_seconds", 20))),
    }


def save_autonomy_config(cfg: dict) -> None:
    write_json(STATE / "autonomy.json", cfg)


def load_goal() -> str:
    try:
        text = (STATE / "goal.txt").read_text(encoding="utf-8").strip()
        return text or "no goal set"
    except Exception:
        return "no goal set"


def save_goal(text: str) -> None:
    (STATE / "goal.txt").write_text(text.strip() + "\n", encoding="utf-8")



def ai_safe(prompt):
    if not prompt.strip():
        return "empty prompt"
    try:
        return ai_reply(prompt)
    except Exception as e:
        AUTONOMY_BACKOFF["fail_count"] += 1
        AUTONOMY_BACKOFF["last_fail"] = time.time()
        return f"ai_error: {e}"

def ai_reply(prompt: str) -> str:
    bump_metric("ai_calls", 1)
    models = [MODEL] + ([FALLBACK_MODEL] if FALLBACK_MODEL else [])
    for model in models:
        try:
            r = subprocess.run(
                ["ollama", "run", model],
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            out = (r.stdout or "").strip()
            if out:
                return out
        except Exception as e:
            log_error(f"ai_reply model={model} error={e}")
            set_last_error(f"ai_reply model={model} error={e}")
    return "(no response)"


def metrics_text() -> str:
    m = load_metrics()
    uptime = int(time.time() - float(m.get("started_at", time.time())))
    return json.dumps(
        {
            "commands": m.get("commands", 0),
            "ai_calls": m.get("ai_calls", 0),
            "errors": m.get("errors", 0),
            "autonomy_ticks": m.get("autonomy_ticks", 0),
            "uptime_seconds": uptime,
            "last_command": m.get("last_command", ""),
            "last_error": m.get("last_error", ""),
        },
        indent=2,
    )


def decide_action(goal: str) -> tuple[str, str]:
    cfg = load_autonomy_config()
    mem = load_memory()
    prompt = f"""You are a minimal local agent.

Goal: {goal}

Known memory:
{json.dumps(mem, indent=2)}

Choose exactly one action:
skip
note: <short text>
reply: <short text>

Rules:
- Keep it short.
- No shell commands.
- No file edits.
- Prefer skip when nothing useful is needed.
- If you use reply, keep it under {cfg["max_reply_chars"]} chars.
- If you use note, keep it under {cfg["max_note_chars"]} chars.
- Output one line only.

Respond with exactly one line.
"""
    out = one_line(ai_reply(prompt), max(cfg["max_note_chars"], cfg["max_reply_chars"]) + 16)

    if out.lower().startswith("note:"):
        return ("note", one_line(out[5:].strip(), cfg["max_note_chars"]))

    if out.lower().startswith("reply:"):
        return ("reply", one_line(out[6:].strip(), cfg["max_reply_chars"]))

    return ("skip", "")


def handle_json_command(obj: dict) -> str:
    action = str(obj.get("cmd", "")).strip()

    if action == "ping":
        return f"pong {time.time()}"
    if action == "status":
        return "hexwatch v6 alive"
    if action == "goal.set":
        value = str(obj.get("value", "")).strip()
        if not value:
            return "goal not updated"
        save_goal(value)
        audit(f"GOAL_SET: {value}")
        return "goal updated"
    if action == "memory.set":
        key = str(obj.get("key", "")).strip()
        value = obj.get("value", "")
        if not key:
            return "memory key missing"
        mem = load_memory()
        mem[key] = value
        save_memory(mem)
        audit(f"MEMORY_SET: {key}")
        return "memory updated"
    if action == "memory.get":
        key = str(obj.get("key", "")).strip()
        mem = load_memory()
        return json.dumps({key: mem.get(key)}, indent=2) if key else json.dumps(mem, indent=2)

    return f"unknown json command: {action}"


def handle(cmd: str) -> str:
    cmd = cmd.strip()
    if not cmd:
        return ""

    bump_metric("commands", 1)
    set_last_command(cmd)

    if cmd.startswith("{") and cmd.endswith("}"):
        try:
            return handle_json_command(json.loads(cmd))
        except Exception as e:
            set_last_error(f"json command parse error: {e}")
            return f"invalid json command: {e}"

    if cmd == "ping":
        return f"pong {time.time()}"
    if cmd == "status":
        return "hexwatch v6 alive"
    if cmd == "version":
        rel = read_json(STATE / "release.json", {})
        return json.dumps(rel, indent=2)

    if cmd == "selftest":
        checks = {
            "monolith_exists": (ROOT / "hexwatch_v6_monolith.py").exists(),
            "inbox_exists": INBOX.exists(),
            "outbox_exists": OUTBOX.exists(),
            "goal_exists": (STATE / "goal.txt").exists(),
            "memory_exists": (STATE / "memory.json").exists(),
            "metrics_exists": (STATE / "metrics.json").exists(),
            "audit_exists": AUDIT_LOG.exists(),
            "daily_exists": (REPORTS / "daily.txt").exists(),
        }
        return json.dumps(checks, indent=2)

    if cmd == "metrics":
        return metrics_text()
    if cmd == "tail status":
        return tail_file(REPORTS / "status.txt", 30)
    if cmd == "tail audit":
        return tail_file(AUDIT_LOG, 30)
    if cmd == "tail main":
        return tail_file(MAIN_LOG, 30)
    if cmd == "report daily":
        write_daily_report()
        return (REPORTS / "daily.txt").read_text(encoding="utf-8").strip()

    if cmd == "report anomaly":
        snap = anomaly_snapshot()
        return json.dumps(snap, indent=2)
    if cmd == "autonomy on":
        cfg = load_autonomy_config()
        cfg["enabled"] = True
        save_autonomy_config(cfg)
        audit("AUTONOMY_ON")
        return "autonomy enabled"
    if cmd == "autonomy off":
        cfg = load_autonomy_config()
        cfg["enabled"] = False
        save_autonomy_config(cfg)
        audit("AUTONOMY_OFF")
        return "autonomy disabled"
    if cmd.startswith("goal "):
        value = cmd[5:].strip()
        if not value:
            return "goal not updated"
        save_goal(value)
        audit(f"GOAL_SET: {value}")
        return "goal updated"
    if cmd.startswith("memory set "):
        rest = cmd[len("memory set "):].strip()
        if " " not in rest:
            return "usage: memory set KEY VALUE"
        key, value = rest.split(" ", 1)
        mem = load_memory()
        mem[key] = value
        save_memory(mem)
        audit(f"MEMORY_SET: {key}")
        return "memory updated"
    if cmd.startswith("memory get "):
        key = cmd[len("memory get "):].strip()
        mem = load_memory()
        return json.dumps({key: mem.get(key)}, indent=2)
    if cmd == "memory":
        return json.dumps(load_memory(), indent=2)
    if cmd.startswith("ask "):
        audit(f"ASK: {cmd[4:80]}")
        return ai_reply(cmd[4:])
    return f"unknown command: {cmd}"


def write_daily_report() -> None:
    m = load_metrics()
    uptime = int(time.time() - float(m.get("started_at", time.time())))
    snap = anomaly_snapshot()
    content = [
        "HEXWATCH DAILY REPORT",
        f"ts: {time.time()}",
        f"uptime_seconds: {uptime}",
        f"commands: {m.get('commands', 0)}",
        f"ai_calls: {m.get('ai_calls', 0)}",
        f"errors: {m.get('errors', 0)}",
        f"autonomy_ticks: {m.get('autonomy_ticks', 0)}",
        f"goal: {load_goal()}",
        f"anomaly_score: {snap['score']}",
        f"anomaly_reasons: {', '.join(snap['reasons']) if snap['reasons'] else 'none'}",
    ]
    (REPORTS / "daily.txt").write_text("\n".join(content) + "\n", encoding="utf-8")


def acquire_lock() -> None:
    if LOCKFILE.exists():
        try:
            old_pid = int(LOCKFILE.read_text(encoding="utf-8").strip())
            os.kill(old_pid, 0)
            raise SystemExit(f"lockfile exists and pid {old_pid} is alive")
        except OSError:
            pass
        except Exception:
            pass

    LOCKFILE.write_text(str(os.getpid()), encoding="utf-8")

    def _cleanup():
        try:
            if LOCKFILE.exists() and LOCKFILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCKFILE.unlink()
        except Exception:
            pass

    atexit.register(_cleanup)


def autonomy_tick() -> None:
    cfg = load_autonomy_config()
    if not cfg["enabled"]:
        return

    now = time.time()
    if now - AUTONOMY_STATE["last_tick"] < cfg["interval_seconds"]:
        return

    AUTONOMY_STATE["last_tick"] = now
    bump_metric("autonomy_ticks", 1)

    if now - AUTONOMY_STATE["last_ai_tick"] < cfg["min_ai_interval_seconds"]:
        audit("AUTO_RATE_LIMIT_SKIP")
        log("AUTO_RATE_LIMIT_SKIP")
        return

    AUTONOMY_STATE["last_ai_tick"] = now
    goal = load_goal()
    action, content = decide_action(goal)

    if action == "note":
        msg = f"[auto-note] {one_line(content, cfg['max_note_chars'])}"
        write_out(msg)
        audit(f"AUTO_NOTE: {msg}")
        log(f"AUTO: {msg}")
    elif action == "reply":
        msg = one_line(content, cfg["max_reply_chars"])
        write_out(msg)
        audit(f"AUTO_REPLY: {msg}")
        log(f"AUTO_REPLY: {msg}")
    else:
        audit("AUTO_SKIP")
        log("AUTO_SKIP")

    write_daily_report()


def main() -> None:
    ensure_dirs()
    acquire_lock()
    log("started")

    last_size = 0

    while True:
        try:
            status_text = [
                "[hexwatch_v6]",
                f"ts: {time.time()}",
                f"pid: {os.getpid()}",
                f"goal: {load_goal()}",
                f"autonomy_enabled: {load_autonomy_config()['enabled']}",
            ]
            (REPORTS / "status.txt").write_text("\n".join(status_text) + "\n", encoding="utf-8")

            if INBOX.exists():
                data = INBOX.read_text(encoding="utf-8")
                if len(data) > last_size:
                    new = data[last_size:].splitlines()
                    last_size = len(data)

                    for line in new:
                        cmd = line.strip()
                        if not cmd:
                            continue
                        out = handle(cmd)
                        if out:
                            write_out(out)
                            log(f"IN: {cmd} | OUT: {out}")
                            audit(f"CMD: {cmd}")

            autonomy_tick()
            time.sleep(1)

        except Exception as e:
            msg = f"loop error: {e}"
            log_error(msg)
            set_last_error(msg)
            time.sleep(1)


if __name__ == "__main__":
    main()

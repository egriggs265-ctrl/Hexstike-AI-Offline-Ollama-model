#!/usr/bin/env python3
"""
hexwatch_v6_monolith.py

Single-file HexWatch v6 monolith.

What it does:
- Creates/maintains the v6 runtime tree
- Polls an inbox file for operator commands
- Writes responses to chat_history.log and outbox files
- Maintains heartbeat/state/report files
- Provides basic command handlers: status, help, ping, tail, run, note, rollup, restart, stop
- Runs background loops for heartbeat and rollup generation
- Avoids external dependencies

Default root:
    ~/hexwatch_v6

Run:
    python3 hexwatch_v6_monolith.py
    python3 hexwatch_v6_monolith.py --root ~/hexwatch_v6 --foreground

Talk to it:
    echo 'status' >> ~/hexwatch_v6/run/chat.inbox
    echo 'tail logs/main.log 40' >> ~/hexwatch_v6/run/chat.inbox
    echo 'run uname -a' >> ~/hexwatch_v6/run/chat.inbox

Notes:
- "run" executes shell commands locally with timeout and output limits.
- This is designed as an operator utility, not a privilege boundary.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import queue
import shlex
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

APP_NAME = "hexwatch_v6"
VERSION = "6.0.0"
DEFAULT_POLL_SECONDS = 2.0
DEFAULT_HEARTBEAT_SECONDS = 5.0
DEFAULT_ROLLUP_SECONDS = 20.0
DEFAULT_CMD_TIMEOUT = 20
DEFAULT_CMD_OUTPUT_LIMIT = 12000
MAX_INBOX_LINE_LEN = 4000
MAX_HISTORY_SNIPPET = 500


@dataclasses.dataclass
class Config:
    root: Path
    poll_seconds: float = DEFAULT_POLL_SECONDS
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS
    rollup_seconds: float = DEFAULT_ROLLUP_SECONDS
    cmd_timeout: int = DEFAULT_CMD_TIMEOUT
    cmd_output_limit: int = DEFAULT_CMD_OUTPUT_LIMIT
    foreground: bool = True


class Paths:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.bin = self.root / "bin"
        self.logs = self.root / "logs"
        self.run = self.root / "run"
        self.state = self.root / "state"
        self.reports = self.root / "reports"
        self.tmp = self.root / "tmp"

        self.main_log = self.logs / "main.log"
        self.chat_history = self.logs / "chat_history.log"
        self.error_log = self.logs / "error.log"

        self.chat_inbox = self.run / "chat.inbox"
        self.chat_outbox = self.run / "chat.outbox"
        self.pid_file = self.run / "monolith.pid"
        self.lock_file = self.run / "monolith.lock"

        self.state_json = self.state / "state.json"
        self.heartbeat = self.state / "heartbeat.json"
        self.commands_jsonl = self.state / "commands.jsonl"

        self.rollup = self.reports / "rollup.txt"
        self.status_txt = self.reports / "status.txt"
        self.last_reply = self.reports / "last_reply.txt"

    def ensure(self) -> None:
        for p in [self.root, self.bin, self.logs, self.run, self.state, self.reports, self.tmp]:
            p.mkdir(parents=True, exist_ok=True)
        for f in [self.main_log, self.chat_history, self.error_log, self.chat_inbox, self.chat_outbox]:
            f.touch(exist_ok=True)


class Logger:
    def __init__(self, paths: Paths):
        self.paths = paths
        self._lock = threading.Lock()

    def _stamp(self) -> str:
        return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")

    def _write(self, file: Path, line: str) -> None:
        with self._lock:
            with file.open("a", encoding="utf-8") as fh:
                fh.write(line.rstrip("\n") + "\n")

    def info(self, msg: str) -> None:
        self._write(self.paths.main_log, f"[{self._stamp()}] INFO  {msg}")

    def error(self, msg: str) -> None:
        self._write(self.paths.error_log, f"[{self._stamp()}] ERROR {msg}")
        self._write(self.paths.main_log, f"[{self._stamp()}] ERROR {msg}")

    def chat(self, direction: str, msg: str) -> None:
        self._write(self.paths.chat_history, f"[{self._stamp()}] {direction.upper():>6} {msg}")


class AtomicFile:
    @staticmethod
    def write_text(path: Path, content: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)

    @staticmethod
    def write_json(path: Path, payload: Dict[str, Any]) -> None:
        AtomicFile.write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


class SingleInstance:
    def __init__(self, pid_file: Path):
        self.pid_file = pid_file

    def acquire(self) -> None:
        if self.pid_file.exists():
            try:
                existing = int(self.pid_file.read_text(encoding="utf-8").strip())
                os.kill(existing, 0)
            except (ValueError, ProcessLookupError, PermissionError, OSError):
                pass
            else:
                raise RuntimeError(f"another instance appears to be running with pid {existing}")
        AtomicFile.write_text(self.pid_file, str(os.getpid()) + "\n")

    def release(self) -> None:
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except OSError:
            pass


class Shell:
    @staticmethod
    def run(command: str, timeout: int, cwd: Optional[Path] = None, output_limit: int = DEFAULT_CMD_OUTPUT_LIMIT) -> Tuple[int, str, str, bool]:
        proc = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            executable="/bin/bash",
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        truncated = False
        if len(stdout) > output_limit:
            stdout = stdout[:output_limit] + "\n...[truncated]"
            truncated = True
        if len(stderr) > output_limit:
            stderr = stderr[:output_limit] + "\n...[truncated]"
            truncated = True
        return proc.returncode, stdout, stderr, truncated


class CommandError(Exception):
    pass


class InboxReader:
    def __init__(self, inbox: Path):
        self.inbox = inbox
        self._offset = 0
        self._inode: Optional[int] = None

    def read_new_lines(self) -> List[str]:
        try:
            stat = self.inbox.stat()
        except FileNotFoundError:
            return []

        inode = getattr(stat, "st_ino", None)
        size = stat.st_size
        if self._inode is None or inode != self._inode or size < self._offset:
            self._inode = inode
            self._offset = 0

        lines: List[str] = []
        with self.inbox.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(self._offset)
            for raw in fh:
                line = raw.rstrip("\n")
                if line.strip():
                    lines.append(line[:MAX_INBOX_LINE_LEN])
            self._offset = fh.tell()
        return lines


class Monolith:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.paths = Paths(cfg.root)
        self.paths.ensure()
        self.log = Logger(self.paths)
        self.instance = SingleInstance(self.paths.pid_file)
        self.inbox = InboxReader(self.paths.chat_inbox)

        self.stop_event = threading.Event()
        self.command_queue: "queue.Queue[str]" = queue.Queue()
        self.threads: List[threading.Thread] = []

        self.started_at = dt.datetime.now(dt.timezone.utc)
        self.last_command_at: Optional[str] = None
        self.last_rollup_at: Optional[str] = None
        self.command_count = 0
        self.last_reply = ""

    def now(self) -> str:
        return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")

    def uptime_seconds(self) -> int:
        return int((dt.datetime.now(dt.timezone.utc) - self.started_at).total_seconds())

    def write_state(self) -> None:
        payload = {
            "app": APP_NAME,
            "version": VERSION,
            "pid": os.getpid(),
            "root": str(self.paths.root),
            "started_at": self.started_at.astimezone().isoformat(timespec="seconds"),
            "uptime_seconds": self.uptime_seconds(),
            "last_command_at": self.last_command_at,
            "last_rollup_at": self.last_rollup_at,
            "command_count": self.command_count,
            "last_reply_sha256": hashlib.sha256(self.last_reply.encode("utf-8")).hexdigest() if self.last_reply else None,
        }
        AtomicFile.write_json(self.paths.state_json, payload)
        AtomicFile.write_json(
            self.paths.heartbeat,
            {
                "ts": self.now(),
                "pid": os.getpid(),
                "uptime_seconds": self.uptime_seconds(),
                "ok": True,
            },
        )

    def append_command_record(self, raw: str, response: str, ok: bool) -> None:
        record = {
            "ts": self.now(),
            "raw": raw,
            "ok": ok,
            "response_preview": response[:MAX_HISTORY_SNIPPET],
        }
        with self.paths.commands_jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def reply(self, msg: str) -> None:
        clean = msg.rstrip() + "\n"
        with self.paths.chat_outbox.open("a", encoding="utf-8") as fh:
            fh.write(clean + "\n")
        AtomicFile.write_text(self.paths.last_reply, clean)
        self.last_reply = clean
        self.log.chat("out", clean.strip())
        self.log.info(f"reply sent ({len(clean)} bytes)")

    def format_status(self) -> str:
        main_tail = tail_file(self.paths.main_log, 8)
        return textwrap.dedent(
            f"""
            [{APP_NAME} {VERSION}]
            ts: {self.now()}
            pid: {os.getpid()}
            root: {self.paths.root}
            uptime_seconds: {self.uptime_seconds()}
            last_command_at: {self.last_command_at or 'none'}
            last_rollup_at: {self.last_rollup_at or 'none'}
            command_count: {self.command_count}
            inbox: {self.paths.chat_inbox}
            outbox: {self.paths.chat_outbox}

            ---- main log tail ----
            {main_tail or '(empty)'}
            """
        ).strip()

    def generate_rollup(self) -> str:
        rollup = textwrap.dedent(
            f"""
            HEXWATCH V6 ROLLUP
            generated: {self.now()}
            pid: {os.getpid()}
            uptime_seconds: {self.uptime_seconds()}
            commands_processed: {self.command_count}
            last_command_at: {self.last_command_at or 'none'}
            last_rollup_at: {self.last_rollup_at or 'none'}

            == FILES ==
            inbox: {self.paths.chat_inbox}
            outbox: {self.paths.chat_outbox}
            main_log: {self.paths.main_log}
            error_log: {self.paths.error_log}
            state_json: {self.paths.state_json}
            heartbeat: {self.paths.heartbeat}

            == MAIN LOG TAIL ==
            {tail_file(self.paths.main_log, 20) or '(empty)'}

            == ERROR LOG TAIL ==
            {tail_file(self.paths.error_log, 20) or '(empty)'}

            == CHAT HISTORY TAIL ==
            {tail_file(self.paths.chat_history, 20) or '(empty)'}
            """
        ).strip() + "\n"
        AtomicFile.write_text(self.paths.rollup, rollup)
        AtomicFile.write_text(self.paths.status_txt, self.format_status() + "\n")
        self.last_rollup_at = self.now()
        return rollup

    def handle_help(self) -> str:
        return textwrap.dedent(
            """
            commands:
              help
              status
              ping
              rollup
              note <text>
              tail <path> [n]
              run <shell command>
              restart
              stop
            """
        ).strip()

    def handle_tail(self, args: List[str]) -> str:
        if not args:
            raise CommandError("usage: tail <path> [n]")
        raw_path = Path(os.path.expanduser(args[0]))
        if not raw_path.is_absolute():
            raw_path = (self.paths.root / raw_path).resolve()
        n = 40
        if len(args) > 1:
            try:
                n = max(1, min(400, int(args[1])))
            except ValueError as exc:
                raise CommandError("tail line count must be an integer") from exc
        if not raw_path.exists():
            raise CommandError(f"not found: {raw_path}")
        return f"== tail {raw_path} ({n}) ==\n" + tail_file(raw_path, n)

    def handle_run(self, args: List[str]) -> str:
        if not args:
            raise CommandError("usage: run <shell command>")
        command = " ".join(args)
        rc, stdout, stderr, truncated = Shell.run(
            command,
            timeout=self.cfg.cmd_timeout,
            cwd=self.paths.root,
            output_limit=self.cfg.cmd_output_limit,
        )
        parts = [
            f"$ {command}",
            f"exit_code: {rc}",
            "",
            "[stdout]",
            stdout.strip() or "(empty)",
            "",
            "[stderr]",
            stderr.strip() or "(empty)",
        ]
        if truncated:
            parts.append("\noutput was truncated")
        return "\n".join(parts).strip()

    def handle_note(self, args: List[str]) -> str:
        if not args:
            raise CommandError("usage: note <text>")
        msg = " ".join(args)
        self.log.info(f"NOTE {msg}")
        return f"noted: {msg}"

    def handle_restart(self) -> str:
        self.log.info("restart requested")
        self.reply("restart requested; stopping current process")
        self.stop_event.set()
        return "restart requested"

    def handle_stop(self) -> str:
        self.log.info("stop requested")
        self.reply("stop requested; shutting down")
        self.stop_event.set()
        return "stop requested"

    def dispatch_command(self, raw: str) -> str:
        parts = shlex.split(raw)
        if not parts:
            return ""
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            return self.handle_help()
        if cmd == "status":
            return self.format_status()
        if cmd == "ping":
            return f"pong {self.now()}"
        if cmd == "rollup":
            return self.generate_rollup().strip()
        if cmd == "note":
            return self.handle_note(args)
        if cmd == "tail":
            return self.handle_tail(args)
        if cmd == "run":
            return self.handle_run(args)
        if cmd == "restart":
            return self.handle_restart()
        if cmd == "stop":
            return self.handle_stop()

        raise CommandError(f"unknown command: {cmd}")

    def inbox_loop(self) -> None:
        self.log.info("inbox loop started")
        while not self.stop_event.is_set():
            try:
                for line in self.inbox.read_new_lines():
                    self.log.chat("in", line)
                    self.command_queue.put(line)
                time.sleep(self.cfg.poll_seconds)
            except Exception as exc:
                self.log.error(f"inbox loop failure: {exc}")
                time.sleep(self.cfg.poll_seconds)
        self.log.info("inbox loop stopped")

    def command_loop(self) -> None:
        self.log.info("command loop started")
        while not self.stop_event.is_set():
            try:
                try:
                    raw = self.command_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                self.command_count += 1
                self.last_command_at = self.now()
                ok = True
                try:
                    response = self.dispatch_command(raw)
                except subprocess.TimeoutExpired:
                    ok = False
                    response = f"command timed out after {self.cfg.cmd_timeout}s"
                except CommandError as exc:
                    ok = False
                    response = f"error: {exc}"
                except Exception as exc:
                    ok = False
                    response = f"unhandled error: {exc}"
                    self.log.error(f"command failure for {raw!r}: {exc}")

                if response:
                    self.reply(response)
                self.append_command_record(raw, response, ok)
                self.write_state()
            except Exception as exc:
                self.log.error(f"command loop failure: {exc}")
        self.log.info("command loop stopped")

    def heartbeat_loop(self) -> None:
        self.log.info("heartbeat loop started")
        while not self.stop_event.is_set():
            try:
                self.write_state()
                AtomicFile.write_text(self.paths.status_txt, self.format_status() + "\n")
            except Exception as exc:
                self.log.error(f"heartbeat loop failure: {exc}")
            self.stop_event.wait(self.cfg.heartbeat_seconds)
        self.log.info("heartbeat loop stopped")

    def rollup_loop(self) -> None:
        self.log.info("rollup loop started")
        while not self.stop_event.is_set():
            try:
                self.generate_rollup()
            except Exception as exc:
                self.log.error(f"rollup loop failure: {exc}")
            self.stop_event.wait(self.cfg.rollup_seconds)
        self.log.info("rollup loop stopped")

    def install_signal_handlers(self) -> None:
        def _handler(signum: int, _frame: Any) -> None:
            self.log.info(f"signal received: {signum}")
            self.stop_event.set()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def start_threads(self) -> None:
        workers = [
            ("inbox", self.inbox_loop),
            ("commands", self.command_loop),
            ("heartbeat", self.heartbeat_loop),
            ("rollup", self.rollup_loop),
        ]
        for name, target in workers:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self.threads.append(t)

    def bootstrap_files(self) -> None:
        install_script = textwrap.dedent(
            f"""#!/usr/bin/env bash
            set -euo pipefail
            ROOT=\"{self.paths.root}\"
            exec python3 \"$ROOT/bin/{APP_NAME}.py\" --root \"$ROOT\" --foreground
            """
        ).strip() + "\n"
        main_copy_target = self.paths.bin / f"{APP_NAME}.py"
        if not main_copy_target.exists():
            try:
                src = Path(__file__).resolve()
                main_copy_target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                os.chmod(main_copy_target, 0o755)
            except Exception as exc:
                self.log.error(f"could not seed bin script copy: {exc}")
        launcher = self.paths.bin / "run.sh"
        AtomicFile.write_text(launcher, install_script)
        os.chmod(launcher, 0o755)

    def run(self) -> int:
        self.paths.ensure()
        self.instance.acquire()
        self.install_signal_handlers()
        self.bootstrap_files()
        self.write_state()
        self.generate_rollup()
        self.log.info(f"{APP_NAME} {VERSION} starting pid={os.getpid()} root={self.paths.root}")
        self.reply(f"{APP_NAME} {VERSION} online at {self.now()}")
        self.start_threads()

        try:
            while not self.stop_event.is_set():
                time.sleep(0.5)
        finally:
            self.log.info("shutdown sequence starting")
            self.stop_event.set()
            deadline = time.time() + 3
            for t in self.threads:
                remaining = max(0.0, deadline - time.time())
                t.join(timeout=remaining)
            try:
                self.write_state()
                self.generate_rollup()
            except Exception as exc:
                self.log.error(f"shutdown write failure: {exc}")
            self.instance.release()
            self.log.info("shutdown complete")
        return 0


def tail_file(path: Path, lines: int) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            data = fh.readlines()
        return "".join(data[-lines:]).rstrip()
    except FileNotFoundError:
        return ""
    except Exception as exc:
        return f"(tail error: {exc})"


def parse_args(argv: Optional[List[str]] = None) -> Config:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} single-file monolith")
    parser.add_argument("--root", default="~/hexwatch_v6", help="runtime root directory")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--heartbeat-seconds", type=float, default=DEFAULT_HEARTBEAT_SECONDS)
    parser.add_argument("--rollup-seconds", type=float, default=DEFAULT_ROLLUP_SECONDS)
    parser.add_argument("--cmd-timeout", type=int, default=DEFAULT_CMD_TIMEOUT)
    parser.add_argument("--cmd-output-limit", type=int, default=DEFAULT_CMD_OUTPUT_LIMIT)
    parser.add_argument("--foreground", action="store_true", default=True)
    args = parser.parse_args(argv)
    return Config(
        root=Path(args.root),
        poll_seconds=args.poll_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        rollup_seconds=args.rollup_seconds,
        cmd_timeout=args.cmd_timeout,
        cmd_output_limit=args.cmd_output_limit,
        foreground=args.foreground,
    )


def main(argv: Optional[List[str]] = None) -> int:
    cfg = parse_args(argv)
    app = Monolith(cfg)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
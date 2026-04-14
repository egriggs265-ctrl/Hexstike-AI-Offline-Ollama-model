```bash
cd ~/hexwatch_v6 && bash <<'EOF'
set -euo pipefail

cat > "$HOME/hexwatch_v6/hexwatch_v6_monolith.py" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
from typing import Any, Dict, List, Optional

APP_NAME = "hexwatch_v6"
VERSION = "6.2.1"
MODEL = os.environ.get("HEXWATCH_MODEL", "llama3")
DEDUP_WINDOW_SECONDS = 5.0

APPROVED_TAIL_TARGETS = {
	"logs/main.log",
	"logs/error.log",
	"logs/chat_history.log",
	"reports/status.txt",
	"reports/rollup.txt",
	"state/state.json",
	"state/heartbeat.json",
}

class Paths:
def __init__(self, root: Path):
self.root = root.expanduser().resolve()
self.bin = self.root / "bin"
self.logs = self.root / "logs"
self.reports = self.root / "reports"
self.run = self.root / "run"
self.state = self.root / "state"
self.tmp = self.root / "tmp"

self.main_log = self.logs / "main.log"
self.error_log = self.logs / "error.log"
self.chat_history = self.logs / "chat_history.log"
self.nohup_log = self.logs / "nohup.log"

self.chat_inbox = self.run / "chat.inbox"
self.chat_outbox = self.run / "chat.outbox"
self.pid_file = self.run / "monolith.pid"

self.status_txt = self.reports / "status.txt"
self.rollup_txt = self.reports / "rollup.txt"
self.last_reply_txt = self.reports / "last_reply.txt"

self.state_json = self.state / "state.json"
self.heartbeat_json = self.state / "heartbeat.json"
self.commands_jsonl = self.state / "commands.jsonl"
self.autonomy_json = self.state / "autonomy.json"
self.goal_txt = self.state / "goal.txt"

def ensure(self) -> None:
for p in [self.root, self.bin, self.logs, self.reports, self.run, self.state, self.tmp]:
	p.mkdir(parents=True, exist_ok=True)
	for f in [
		self.main_log, self.error_log, self.chat_history, self.nohup_log,
self.chat_inbox, self.chat_outbox, self.commands_jsonl, self.goal_txt
	]:
	f.touch(exist_ok=True)
	
	class AtomicFile:
	@staticmethod
	def write_text(path: Path, content: str) -> None:
	tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
	with tmp.open("w", encoding="utf-8") as fh:
	fh.write(content)
	os.replace(tmp, path)
	
	@staticmethod
	def write_json(path: Path, payload: Dict[str, Any]) -> None:
	AtomicFile.write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
	
	class Logger:
	def __init__(self, paths: Paths):
	self.paths = paths
	self.lock = threading.Lock()
	
	def stamp(self) -> str:
	return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
	
	def _write(self, path: Path, line: str) -> None:
	with self.lock:
	with path.open("a", encoding="utf-8") as fh:
	fh.write(line.rstrip("\n") + "\n")
	
	def info(self, msg: str) -> None:
	self._write(self.paths.main_log, f"[{self.stamp()}] INFO  {msg}")
	
	def error(self, msg: str) -> None:
	self._write(self.paths.error_log, f"[{self.stamp()}] ERROR {msg}")
	self._write(self.paths.main_log, f"[{self.stamp()}] ERROR {msg}")
	
	def chat(self, direction: str, msg: str) -> None:
	self._write(self.paths.chat_history, f"[{self.stamp()}] {direction.upper():>6} {msg}")
	
	class SingleInstance:
	def __init__(self, pid_file: Path):
	self.pid_file = pid_file
	
	def acquire(self) -> None:
	if self.pid_file.exists():
		try:
		existing = int(self.pid_file.read_text(encoding="utf-8").strip())
		os.kill(existing, 0)
		except Exception:
		pass
		else:
			raise RuntimeError(f"another instance appears to be running with pid {existing}")
			AtomicFile.write_text(self.pid_file, f"{os.getpid()}\n")
			
			def release(self) -> None:
			try:
			self.pid_file.unlink()
			except FileNotFoundError:
			pass
			
			class InboxReader:
			def __init__(self, path: Path):
			self.path = path
			self.offset = 0
			self.inode: Optional[int] = None
			
			def read_new_lines(self) -> List[str]:
			try:
			st = self.path.stat()
			except FileNotFoundError:
			return []
			
			inode = getattr(st, "st_ino", None)
			size = st.st_size
			
			if self.inode is None:
				self.inode = inode
				self.offset = size
				return []
				
				if inode != self.inode or size < self.offset:
					self.inode = inode
					self.offset = size
					return []
					
					out: List[str] = []
					with self.path.open("r", encoding="utf-8", errors="replace") as fh:
					fh.seek(self.offset)
					for raw in fh:
						line = raw.rstrip("\n")
						if line.strip():
							out.append(line[:4000])
							self.offset = fh.tell()
							return out
							
							class LocalAIResponder:
							def __init__(self, model: str = MODEL):
							self.model = model
							
							def available(self) -> bool:
							try:
							r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
							return r.returncode == 0
							except Exception:
							return False
							
							def reply(self, system_instructions: str, user_text: str) -> str:
							prompt = f"{system_instructions}\n\n{user_text}"
							try:
							r = subprocess.run(
								["ollama", "run", self.model],
						  input=prompt,
						  capture_output=True,
						  text=True,
							)
							out = (r.stdout or "").strip()
							err = (r.stderr or "").strip()
							if r.returncode != 0:
								return f"local AI error: {err or 'ollama run failed'}"
								return out or "(no response)"
								except Exception as e:
								return f"local AI error: {e}"
								
								def decide(self, system_instructions: str, payload: str) -> Dict[str, Any]:
								prompt = f"{system_instructions}\n\n{payload}\n\nReturn JSON only."
								try:
								r = subprocess.run(
									["ollama", "run", self.model],
						   input=prompt,
						   capture_output=True,
						   text=True,
								)
								raw = (r.stdout or "").strip()
								start = raw.find("{")
									end = raw.rfind("}")
									if start != -1 and end != -1 and end > start:
										return json.loads(raw[start:end+1])
										except Exception:
										pass
										return {"type": "reply", "message": "AI decision failed"}
										
										def tail_file(path: Path, n: int) -> str:
										try:
										with path.open("r", encoding="utf-8", errors="replace") as fh:
										lines = fh.readlines()
										return "".join(lines[-n:]).rstrip()
										except FileNotFoundError:
										return ""
										except Exception as e:
										return f"(tail error: {e})"
										
										class Monolith:
										def __init__(self, root: Path):
										self.paths = Paths(root)
										self.paths.ensure()
										self.log = Logger(self.paths)
										self.instance = SingleInstance(self.paths.pid_file)
										self.inbox = InboxReader(self.paths.chat_inbox)
										self.ai = LocalAIResponder()
										
										self.stop_event = threading.Event()
										self.queue: "queue.Queue[str]" = queue.Queue()
										self.threads: List[threading.Thread] = []
										
										self.started_at = dt.datetime.now(dt.timezone.utc)
										self.last_command_at: Optional[str] = None
										self.last_rollup_at: Optional[str] = None
										self.command_count = 0
										self.last_reply = ""
										self.seen_times: Dict[str, float] = {}
										
										self.system_instructions = textwrap.dedent("""
										You are HexWatch, a concise local operator assistant.
										You help monitor a contained runtime.
										Answer directly and briefly.
										Never claim actions you did not actually take.
										Never request arbitrary shell execution.
										""").strip()
										
										def now(self) -> str:
										return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
										
										def uptime(self) -> int:
										return int((dt.datetime.now(dt.timezone.utc) - self.started_at).total_seconds())
										
										def goal_text(self) -> str:
										try:
										return self.paths.goal_txt.read_text(encoding="utf-8").strip()
										except Exception:
										return ""
										
										def read_autonomy_state(self) -> Dict[str, Any]:
										try:
										return json.loads(self.paths.autonomy_json.read_text(encoding="utf-8"))
										except Exception:
										return {"enabled": False, "last_tick": None}
										
										def write_autonomy_state(self, enabled: bool) -> None:
										AtomicFile.write_json(self.paths.autonomy_json, {"enabled": enabled, "last_tick": self.now()})
										
										def write_state(self) -> None:
										AtomicFile.write_json(self.paths.state_json, {
											"app": APP_NAME,
											"version": VERSION,
											"pid": os.getpid(),
															  "root": str(self.paths.root),
															  "started_at": self.started_at.astimezone().isoformat(timespec="seconds"),
															  "uptime_seconds": self.uptime(),
															  "last_command_at": self.last_command_at,
															  "last_rollup_at": self.last_rollup_at,
															  "command_count": self.command_count,
															  "ai_available": self.ai.available(),
										})
										AtomicFile.write_json(self.paths.heartbeat_json, {
											"ts": self.now(),
															  "pid": os.getpid(),
															  "uptime_seconds": self.uptime(),
															  "ok": True,
										})
										
										def append_command_record(self, raw: str, response: str, ok: bool) -> None:
										rec = {
											"ts": self.now(),
											"raw": raw,
											"ok": ok,
											"response_preview": response[:500],
										}
										with self.paths.commands_jsonl.open("a", encoding="utf-8") as fh:
										fh.write(json.dumps(rec, sort_keys=True) + "\n")
										
										def reply(self, msg: str) -> None:
										clean = msg.rstrip() + "\n"
										with self.paths.chat_outbox.open("a", encoding="utf-8") as fh:
										fh.write(clean + "\n")
										AtomicFile.write_text(self.paths.last_reply_txt, clean)
										self.last_reply = clean
										self.log.chat("out", clean.strip())
										self.log.info(f"reply sent ({len(clean)} bytes)")
										
										def format_status(self) -> str:
										auto = self.read_autonomy_state()
										return textwrap.dedent(f"""
										[{APP_NAME} {VERSION}]
										ts: {self.now()}
										pid: {os.getpid()}
										root: {self.paths.root}
										uptime_seconds: {self.uptime()}
										last_command_at: {self.last_command_at or 'none'}
										last_rollup_at: {self.last_rollup_at or 'none'}
										command_count: {self.command_count}
										ai_available: {self.ai.available()}
										autonomy_enabled: {auto.get('enabled', False)}
										goal: {self.goal_text() or '(none)'}
										inbox: {self.paths.chat_inbox}
										outbox: {self.paths.chat_outbox}
										
										---- main log tail ----
										{tail_file(self.paths.main_log, 8) or '(empty)'}
										""").strip()
										
										def generate_rollup(self) -> str:
										text = textwrap.dedent(f"""
										HEXWATCH V6 ROLLUP
										generated: {self.now()}
										pid: {os.getpid()}
										uptime_seconds: {self.uptime()}
										commands_processed: {self.command_count}
										last_command_at: {self.last_command_at or 'none'}
										last_rollup_at: {self.last_rollup_at or 'none'}
										ai_available: {self.ai.available()}
										autonomy_enabled: {self.read_autonomy_state().get('enabled', False)}
										goal: {self.goal_text() or '(none)'}
										
										== MAIN LOG TAIL ==
										{tail_file(self.paths.main_log, 20) or '(empty)'}
										
										== ERROR LOG TAIL ==
										{tail_file(self.paths.error_log, 20) or '(empty)'}
										
										== CHAT HISTORY TAIL ==
										{tail_file(self.paths.chat_history, 20) or '(empty)'}
										""").strip() + "\n"
										AtomicFile.write_text(self.paths.rollup_txt, text)
										AtomicFile.write_text(self.paths.status_txt, self.format_status() + "\n")
										self.last_rollup_at = self.now()
										return text
										
										def ai_reply(self, text: str) -> str:
										if not self.ai.available():
											return "local AI is unavailable; install Ollama and make sure llama3 is pulled"
											prompt = textwrap.dedent(f"""
											Current status snapshot:
											{self.format_status()}
											
											User message:
											{text}
											""").strip()
											return self.ai.reply(self.system_instructions, prompt)
											
											def approved_tail(self, rel_path: str, lines: int = 80) -> str:
											rel = rel_path.strip().lstrip("/")
											if rel not in APPROVED_TAIL_TARGETS:
												return f"tail target not approved: {rel}"
												target = (self.paths.root / rel).resolve()
												return f"== tail {target} ({lines}) ==\n" + tail_file(target, lines)
												
												def perform_ai_action(self, action: Dict[str, Any]) -> str:
												kind = str(action.get("type", "reply")).strip().lower()
												if kind == "reply":
													return str(action.get("message", "")).strip() or "(empty reply)"
													if kind == "status":
														return self.format_status()
														if kind == "rollup":
															return self.generate_rollup().strip()
															if kind == "note":
																msg = str(action.get("message", "")).strip()
																self.log.info(f"NOTE {msg}")
																return f"noted: {msg}" if msg else "note action missing message"
																if kind == "tail":
																	return self.approved_tail(str(action.get("path", "")).strip(), int(action.get("lines", 80)))
																	return f"unapproved action: {kind}"
																	
																	def ai_decide_action(self, message: str) -> str:
																	if not self.ai.available():
																		return "local AI is unavailable; install Ollama and make sure llama3 is pulled"
																		schema = textwrap.dedent("""
																		You are HexWatch.
																		Return a JSON object only.
																		Choose one action from this whitelist:
																		- {"type":"reply","message":"..."}
																		- {"type":"status"}
																		- {"type":"rollup"}
																		- {"type":"note","message":"..."}
																		- {"type":"tail","path":"logs/main.log","lines":80}
																		Approved tail paths:
																		logs/main.log, logs/error.log, logs/chat_history.log, reports/status.txt, reports/rollup.txt, state/state.json, state/heartbeat.json
																		Never choose run or arbitrary shell execution.
																		Keep the action useful and concise.
																		""").strip()
																		payload = textwrap.dedent(f"""
																		Status snapshot:
																		{self.format_status()}
																		
																		Message:
																		{message}
																		""").strip()
																		return self.perform_ai_action(self.ai.decide(schema, payload))
																		
																		def handle_help(self) -> str:
																		return textwrap.dedent("""
																		commands:
																		help
																		status
																		ping
																		rollup
																		note <text>
																		goal <text>
																		autonomy on
																		autonomy off
																		ask <text>
																		tail <path> [n]
																		run <shell command>
																		restart
																		stop
																		""").strip()
																		
																		def handle_run(self, args: List[str]) -> str:
																		if not args:
																			return "error: usage: run <shell command>"
																			command = " ".join(args)
																			try:
																			r = subprocess.run(
																				command,
									  shell=True,
									  text=True,
									  capture_output=True,
									  timeout=20,
									  cwd=str(self.paths.root),
																							   executable="/bin/bash",
																			)
																			stdout = r.stdout or ""
																			stderr = r.stderr or ""
																			return textwrap.dedent(f"""
																			$ {command}
																			exit_code: {r.returncode}
																			
																			[stdout]
																			{stdout.strip() or '(empty)'}
																			
																			[stderr]
																			{stderr.strip() or '(empty)'}
																			""").strip()
																			except subprocess.TimeoutExpired:
																			return "command timed out after 20s"
																			
																			def dispatch(self, raw: str) -> str:
																			try:
																			parts = shlex.split(raw)
																			except ValueError:
																			return self.ai_decide_action(raw)
																			
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
																									msg = " ".join(args).strip()
																									if not msg:
																										return "error: usage: note <text>"
																										self.log.info(f"NOTE {msg}")
																										return f"noted: {msg}"
																										if cmd == "goal":
																											msg = " ".join(args).strip()
																											if not msg:
																												return "error: usage: goal <text>"
																												AtomicFile.write_text(self.paths.goal_txt, msg + "\n")
																												return f"goal set: {msg}"
																												if cmd == "autonomy":
																													if not args or args[0].lower() not in {"on", "off"}:
																														return "error: usage: autonomy on|off"
																														enabled = args[0].lower() == "on"
																														self.write_autonomy_state(enabled)
																														return f"autonomy {'enabled' if enabled else 'disabled'}"
																														if cmd == "ask":
																															return self.ai_reply(" ".join(args).strip())
																															if cmd == "tail":
																																if not args:
																																	return "error: usage: tail <path> [n]"
																																	path = args[0]
																																	lines = int(args[1]) if len(args) > 1 else 40
																																	return self.approved_tail(path, lines)
																																	if cmd == "run":
																																		return self.handle_run(args)
																																		if cmd == "restart":
																																			self.reply("restart requested; stopping current process")
																																			self.stop_event.set()
																																			return "restart requested"
																																			if cmd == "stop":
																																				self.reply("stop requested; shutting down")
																																				self.stop_event.set()
																																				return "stop requested"
																																				
																																				return self.ai_decide_action(raw)
																																				
																																				def inbox_loop(self) -> None:
																																				self.log.info("inbox loop started")
																																				while not self.stop_event.is_set():
																																					try:
																																					for line in self.inbox.read_new_lines():
																																						self.log.chat("in", line)
																																						self.queue.put(line)
																																						time.sleep(1.0)
																																						except Exception as e:
																																						self.log.error(f"inbox loop failure: {e}")
																																						time.sleep(1.0)
																																						self.log.info("inbox loop stopped")
																																						
																																						def command_loop(self) -> None:
																																						self.log.info("command loop started")
																																						while not self.stop_event.is_set():
																																							try:
																																							try:
																																							raw = self.queue.get(timeout=0.5)
																																							except queue.Empty:
																																							continue
																																							
																																							h = hashlib.sha256(raw.encode()).hexdigest()
																																							now = time.time()
																																							if now - self.seen_times.get(h, 0.0) < DEDUP_WINDOW_SECONDS:
																																								self.log.info(f"duplicate command skipped: {raw}")
																																								continue
																																								self.seen_times[h] = now
																																								
																																								self.command_count += 1
																																								self.last_command_at = self.now()
																																								ok = True
																																								try:
																																								response = self.dispatch(raw)
																																								except Exception as e:
																																								ok = False
																																								response = f"unhandled error: {e}"
																																								self.log.error(f"command failure for {raw!r}: {e}")
																																								
																																								if response:
																																									self.reply(response)
																																									self.append_command_record(raw, response, ok)
																																									self.write_state()
																																									except Exception as e:
																																									self.log.error(f"command loop failure: {e}")
																																									self.log.info("command loop stopped")
																																									
																																									def heartbeat_loop(self) -> None:
																																									self.log.info("heartbeat loop started")
																																									while not self.stop_event.is_set():
																																										try:
																																										self.write_state()
																																										AtomicFile.write_text(self.paths.status_txt, self.format_status() + "\n")
																																										except Exception as e:
																																										self.log.error(f"heartbeat loop failure: {e}")
																																										self.stop_event.wait(5.0)
																																										self.log.info("heartbeat loop stopped")
																																										
																																										def rollup_loop(self) -> None:
																																										self.log.info("rollup loop started")
																																										while not self.stop_event.is_set():
																																											try:
																																											self.generate_rollup()
																																											except Exception as e:
																																											self.log.error(f"rollup loop failure: {e}")
																																											self.stop_event.wait(20.0)
																																											self.log.info("rollup loop stopped")
																																											
																																											def autonomy_loop(self) -> None:
																																											self.log.info("autonomy loop started")
																																											while not self.stop_event.is_set():
																																												try:
																																												auto = self.read_autonomy_state()
																																												goal = self.goal_text()
																																												if not self.ai.available() or not auto.get("enabled") or not goal:
																																													self.stop_event.wait(30.0)
																																													continue
																																													
																																													payload = textwrap.dedent(f"""
																																													Goal:
																																													{goal}
																																													
																																													Current status:
																																													{self.format_status()}
																																													
																																													Recent chat history:
																																													{tail_file(self.paths.chat_history, 20) or '(empty)'}
																																													
																																													Recent errors:
																																													{tail_file(self.paths.error_log, 10) or '(empty)'}
																																													""").strip()
																																													
																																													decision = self.ai.decide(textwrap.dedent("""
																																													You are HexWatch autonomous mode.
																																													Return a JSON object only.
																																													Choose one action from:
																																													- {"type":"reply","message":"..."}
																																													- {"type":"status"}
																																													- {"type":"rollup"}
																																													- {"type":"note","message":"..."}
																																													- {"type":"tail","path":"logs/main.log","lines":80}
																																													- {"type":"reply","message":""}
																																													Never request raw shell commands.
																																													Only send a message when something useful changed, or a short proactive update helps.
																																													""").strip(), payload)
																																													
																																													output = self.perform_ai_action(decision)
																																													if output and output.strip() and output.strip() != "(empty reply)":
																																														self.reply(output)
																																														self.write_autonomy_state(True)
																																														self.write_state()
																																														except Exception as e:
																																														self.log.error(f"autonomy loop failure: {e}")
																																														self.stop_event.wait(30.0)
																																														self.log.info("autonomy loop stopped")
																																														
																																														def install_signal_handlers(self) -> None:
																																														def handler(signum: int, _frame: Any) -> None:
																																														self.log.info(f"signal received: {signum}")
																																														self.stop_event.set()
																																														signal.signal(signal.SIGINT, handler)
																																														signal.signal(signal.SIGTERM, handler)
																																														
																																														def bootstrap_files(self) -> None:
																																														run_sh = textwrap.dedent("""\
#!/usr/bin/env bash
set -euo pipefail
ROOT="${HOME}/hexwatch_v6"
exec python3 "$ROOT/hexwatch_v6_monolith.py" --root "$ROOT" --foreground
""")
																																														talk_sh = textwrap.dedent("""\
#!/usr/bin/env bash
set -euo pipefail
ROOT="${HOME}/hexwatch_v6"
OUT="$ROOT/run/chat.outbox"
IN="$ROOT/run/chat.inbox"
MSG="${*:-status}"

mkdir -p "$ROOT/run"
touch "$OUT" "$IN"

before=$(wc -l < "$OUT" 2>/dev/null || echo 0)
printf '%s\n' "$MSG" >> "$IN"
echo "[sent] $MSG"
sleep 2
after=$(wc -l < "$OUT" 2>/dev/null || echo 0)

if [ "$after" -gt "$before" ]; then
	sed -n "$((before+1)),$((after))p" "$OUT"
	else
		echo "[no new reply yet]"
		fi
		""")
																																														AtomicFile.write_text(self.paths.bin / "run.sh", run_sh)
																																														AtomicFile.write_text(self.paths.bin / "talk.sh", talk_sh)
																																														os.chmod(self.paths.bin / "run.sh", 0o755)
																																														os.chmod(self.paths.bin / "talk.sh", 0o755)
																																														
																																														if not self.paths.autonomy_json.exists():
																																															self.write_autonomy_state(False)
																																															if not self.goal_text():
																																																AtomicFile.write_text(
																																																	self.paths.goal_txt,
																	  "watch system health and respond when something important changes\n",
																																																)
																																																
																																																def run(self) -> int:
																																																self.instance.acquire()
																																																self.install_signal_handlers()
																																																self.bootstrap_files()
																																																self.write_state()
																																																self.generate_rollup()
																																																self.log.info(f"{APP_NAME} {VERSION} starting pid={os.getpid()} root={self.paths.root}")
																																																self.reply(f"{APP_NAME} {VERSION} online at {self.now()}")
																																																
																																																for name, fn in [
																																																	("inbox", self.inbox_loop),
																																																	("commands", self.command_loop),
																																																	("heartbeat", self.heartbeat_loop),
																																																	("rollup", self.rollup_loop),
																																																	("autonomy", self.autonomy_loop),
																																																]:
																																																t = threading.Thread(target=fn, name=name, daemon=True)
																																																t.start()
																																																self.threads.append(t)
																																																
																																																try:
																																																while not self.stop_event.is_set():
																																																	time.sleep(0.5)
																																																	finally:
																																																	self.log.info("shutdown sequence starting")
																																																	self.stop_event.set()
																																																	deadline = time.time() + 3
																																																	for t in self.threads:
																																																		t.join(timeout=max(0.0, deadline - time.time()))
																																																		try:
																																																		self.write_state()
																																																		self.generate_rollup()
																																																		except Exception as e:
																																																		self.log.error(f"shutdown write failure: {e}")
																																																		self.instance.release()
																																																		self.log.info("shutdown complete")
																																																		return 0
																																																		
																																																		def main() -> int:
																																																		ap = argparse.ArgumentParser()
																																																		ap.add_argument("--root", default="~/hexwatch_v6")
																																																		ap.add_argument("--foreground", action="store_true", default=True)
																																																		args = ap.parse_args()
																																																		return Monolith(Path(args.root)).run()
																																																		
																																																		if __name__ == "__main__":
																																																			sys.exit(main())
																																																			PY
																																																			
																																																			chmod +x "$HOME/hexwatch_v6/hexwatch_v6_monolith.py"
																																																			python3 -m py_compile "$HOME/hexwatch_v6/hexwatch_v6_monolith.py"
																																																			
																																																			pkill -9 -f '/home/parrot/hexwatch_v6/hexwatch_v6_monolith.py' 2>/dev/null || true
																																																			rm -f "$HOME/hexwatch_v6/run/monolith.pid"
																																																			: > "$HOME/hexwatch_v6/run/chat.inbox"
																																																			: > "$HOME/hexwatch_v6/run/chat.outbox"
																																																			
																																																			nohup python3 "$HOME/hexwatch_v6/hexwatch_v6_monolith.py" --root "$HOME/hexwatch_v6" > "$HOME/hexwatch_v6/logs/nohup.log" 2>&1 &
																																																			sleep 3
																																																			
																																																			echo '=== PROCESS ==='
																																																			pgrep -af 'hexwatch_v6_monolith.py' || true
																																																			echo
																																																			echo '=== NOHUP LOG ==='
																																																			tail -n 40 "$HOME/hexwatch_v6/logs/nohup.log" 2>/dev/null || true
																																																			echo
																																																			echo '=== TEST ==='
																																																			"$HOME/hexwatch_v6/bin/talk.sh" "hello"
																																																			EOF
																																																			=== PROCESS ===
																																																			4534 python3 /home/parrot/hexwatch_v6/hexwatch_v6_monolith.py --root /home/parrot/hexwatch_v6
																																																			
																																																			=== NOHUP LOG ===
																																																			
																																																			=== TEST ===
																																																			[sent] hello
																																																			local AI error: Command '['ollama', 'run', 'llama3']' timed out after 120 seconds
																																																			┌─[parrot@parrot]─[~/hexwatch_v6]
																																																			└──╼ $data, I have no fear. All right? because this is a local thing, it should not have a time out. we're not online
																																																			git add .
																																																			git commit -m "v6.2.1"
																																																			okay got it — because this is local AI, there’s no reason to hard timeout the model call. the 120s timeout is what killed the reply, not the loop itself.
																																																			
																																																			for local ollama, the clean move is:
																																																				- keep short timeouts for shell commands
																																																				- remove or greatly increase timeout for AI generation
																																																				- optionally use a smaller/faster model later if needed
																																																				
																																																				run this one-liner to remove the ollama timeout from both reply() and decide():
																																																				
																																																				perl -0pi -e 's/,\s*timeout=120//g' ~/hexwatch_v6/hexwatch_v6_monolith.py
																																																				
																																																				then restart clean:
																																																				
																																																				pkill -9 -f "/home/parrot/hexwatch_v6/hexwatch_v6_monolith.py" 2>/dev/null || true
																																																				rm -f ~/hexwatch_v6/run/monolith.pid
																																																				nohup python3 ~/hexwatch_v6/hexwatch_v6_monolith.py --root ~/hexwatch_v6 > ~/hexwatch_v6/logs/nohup.log 2>&1 &
																																																				sleep 3
																																																				
																																																				then test again:
																																																				
																																																				~/hexwatch_v6/bin/talk.sh "hello"
																																																				~/hexwatch_v6/bin/talk.sh "ask what is your current status"
																																																				
																																																				if llama3 still feels too slow on CPU, switch to a smaller local model:
																																																					
																																																					ollama pull phi3:mini
																																																					HEXWATCH_MODEL="phi3:mini" nohup python3 ~/hexwatch_v6/hexwatch_v6_monolith.py --root ~/hexwatch_v6 > ~/hexwatch_v6/logs/nohup.log 2>&1 &
																																																					
																																																					the important part: your loop is alive now. the only failure was generation timing, not architecture.
																																																					author identity unknown
																																																					
																																																					*** Please tell me who you are.
																																																					
																																																					Run
																																																					
																																																					git config --global user.email "you@example.com"
																																																					git config --global user.name "Your Name"
																																																					
																																																					to set your account's default identity.
																																																					Omit --global to set the identity only in this repository.
																																																					
																																																					fatal: unable to auto-detect email address (got 'parrot@parrot.(none)')
																																																					┌─[✗]─[parrot@parrot]─[~/hexwatch_v6]
																																																					└──╼ $♀♀♀♀assistant to=canmore.update_textdoc კომენტary  ฝ่ายขายรายการ
																																																					{"updates":[{"pattern":"(?s).*","replacement":"#!/usr/bin/env python3\nfrom __future__ import annotations\n\nimport argparse\nimport datetime as dt\nimport hashlib\nimport json\nimport os\nimport queue\nimport shlex\nimport signal\nimport subprocess\nimport sys\nimport textwrap\nimport threading\nimport time\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional\n\nAPP_NAME = \"hexwatch_v6\"\nVERSION = \"6.2.2\"\nMODEL = os.environ.get(\"HEXWATCH_MODEL\", \"llama3\")\nDEDUP_WINDOW_SECONDS = 5.0\n\nAPPROVED_TAIL_TARGETS = {\n    \"logs/main.log\",\n    \"logs/error.log\",\n    \"logs/chat_history.log\",\n    \"reports/status.txt\",\n    \"reports/rollup.txt\",\n    \"state/state.json\",\n    \"state/heartbeat.json\",\n}\n\nclass Paths:\n    def __init__(self, root: Path):\n        self.root = root.expanduser().resolve()\n        self.bin = self.root / \"bin\"\n        self.logs = self.root / \"logs\"\n        self.reports = self.root / \"reports\"\n        self.run = self.root / \"run\"\n        self.state = self.root / \"state\"\n        self.tmp = self.root / \"tmp\"\n\n        self.main_log = self.logs / \"main.log\"\n        self.error_log = self.logs / \"error.log\"\n        self.chat_history = self.logs / \"chat_history.log\"\n        self.nohup_log = self.logs / \"nohup.log\"\n\n        self.chat_inbox = self.run / \"chat.inbox\"\n        self.chat_outbox = self.run / \"chat.outbox\"\n        self.pid_file = self.run / \"monolith.pid\"\n\n        self.status_txt = self.reports / \"status.txt\"\n        self.rollup_txt = self.reports / \"rollup.txt\"\n        self.last_reply_txt = self.reports / \"last_reply.txt\"\n\n        self.state_json = self.state / \"state.json\"\n        self.heartbeat_json = self.state / \"heartbeat.json\"\n        self.commands_jsonl = self.state / \"commands.jsonl\"\n        self.autonomy_json = self.state / \"autonomy.json\"\n        self.goal_txt = self.state / \"goal.txt\"\n\n    def ensure(self) -> None:\n        for p in [self.root, self.bin, self.logs, self.reports, self.run, self.state, self.tmp]:\n            p.mkdir(parents=True, exist_ok=True)\n        for f in [\n            self.main_log, self.error_log, self.chat_history, self.nohup_log,\n            self.chat_inbox, self.chat_outbox, self.commands_jsonl, self.goal_txt\n        ]:\n            f.touch(exist_ok=True)\n\nclass AtomicFile:\n    @staticmethod\n    def write_text(path: Path, content: str) -> None:\n        tmp = path.with_suffix(path.suffix + f\".{os.getpid()}.{threading.get_ident()}.tmp\")\n        with tmp.open(\"w\", encoding=\"utf-8\") as fh:\n            fh.write(content)\n        os.replace(tmp, path)\n\n    @staticmethod\n    def write_json(path: Path, payload: Dict[str, Any]) -> None:\n        AtomicFile.write_text(path, json.dumps(payload, indent=2, sort_keys=True) + \"\\n\")\n\nclass Logger:\n    def __init__(self, paths: Paths):\n        self.paths = paths\n        self.lock = threading.Lock()\n\n    def stamp(self) -> str:\n        return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec=\"seconds\")\n\n    def _write(self, path: Path, line: str) -> None:\n        with self.lock:\n            with path.open(\"a\", encoding=\"utf-8\") as fh:\n                fh.write(line.rstrip(\"\\n\") + \"\\n\")\n\n    def info(self, msg: str) -> None:\n        self._write(self.paths.main_log, f\"[{self.stamp()}] INFO  {msg}\")\n\n    def error(self, msg: str) -> None:\n        self._write(self.paths.error_log, f\"[{self.stamp()}] ERROR {msg}\")\n        self._write(self.paths.main_log, f\"[{self.stamp()}] ERROR {msg}\")\n\n    def chat(self, direction: str, msg: str) -> None:\n        self._write(self.paths.chat_history, f\"[{self.stamp()}] {direction.upper():>6} {msg}\")\n\nclass SingleInstance:\n    def __init__(self, pid_file: Path):\n        self.pid_file = pid_file\n\n    def acquire(self) -> None:\n        if self.pid_file.exists():\n            try:\n                existing = int(self.pid_file.read_text(encoding=\"utf-8\").
strip())\n                os.kill(existing, 0)\n            except Exception:\n                pass\n            else:\n                raise RuntimeError(f\"another instance appears to be running with pid {existing}\")\n        AtomicFile.write_text(self.pid_file, f\"{os.getpid()}\\n\")\n\n    def release(self) -> None:\n        try:\n            self.pid_file.unlink()\n        except FileNotFoundError:\n            pass\n\nclass InboxReader:\n    def __init__(self, path: Path):\n        self.path = path\n        self.offset = 0\n        self.inode: Optional[int] = None\n\n    def read_new_lines(self) -> List[str]:\n        try:\n            st = self.path.stat()\n        except FileNotFoundError:\n            return []\n\n        inode = getattr(st, \"st_ino\", None)\n        size = st.st_size\n\n        if self.inode is None:\n            self.inode = inode\n            self.offset = size\n            return []\n\n        if inode != self.inode or size < self.offset:\n            self.inode = inode\n            self.offset = size\n            return []\n\n        out: List[str] = []\n        with self.path.open(\"r\", encoding=\"utf-8\", errors=\"replace\") as fh:\n            fh.seek(self.offset)\n            for raw in fh:\n                line = raw.rstrip(\"\\n\")\n                if line.strip():\n                    out.append(line[:4000])\n            self.offset = fh.tell()\n        return out\n\nclass LocalAIResponder:\n    def __init__(self, model: str = MODEL):\n        self.model = model\n\n    def available(self) -> bool:\n        try:\n            r = subprocess.run([\"ollama\", \"list\"], capture_output=True, text=True, timeout=5)\n            return r.returncode == 0\n        except Exception:\n            return False\n\n    def reply(self, system_instructions: str, user_text: str) -> str:\n        prompt = f\"{system_instructions}\\n\\n{user_text}\"\n        try:\n            r = subprocess.run(\n                [\"ollama\", \"run\", self.model],\n                input=prompt,\n                capture_output=True,\n                text=True,\n            )\n            out = (r.stdout or \"\").strip()\n            err = (r.stderr or \"\").strip()\n            if r.returncode != 0:\n                return f\"local AI error: {err or 'ollama run failed'}\"\n            return out or \"(no response)\"\n        except Exception as e:\n            return f\"local AI error: {e}\"\n\n    def decide(self, system_instructions: str, payload: str) -> Dict[str, Any]:\n        prompt = f\"{system_instructions}\\n\\n{payload}\\n\\nReturn JSON only.\"\n        try:\n            r = subprocess.run(\n                [\"ollama\", \"run\", self.model],\n                input=prompt,\n                capture_output=True,\n                text=True,\n            )\n            raw = (r.stdout or \"\").strip()\n            start = raw.find(\"{\")\n            end = raw.rfind(\"}\")\n            if start != -1 and end != -1 and end > start:\n                return json.loads(raw[start:end+1])\n        except Exception:\n            pass\n        return {\"type\": \"reply\", \"message\": \"AI decision failed\"}\n\ndef tail_file(path: Path, n: int) -> str:\n    try:\n        with path.open(\"r\", encoding=\"utf-8\", errors=\"replace\") as fh:\n            lines = fh.readlines()\n        return \"\".join(lines[-n:]).rstrip()\n    except FileNotFoundError:\n        return \"\"\n    except Exception as e:\n        return f\"(tail error: {e})\"\n\nclass Monolith:\n    def __init__(self, root: Path):\n        self.paths = Paths(root)\n        self.paths.ensure()\n        self.log = Logger(self.paths)\n        self.instance = SingleInstance(self.paths.pid_file)\n        self.inbox = InboxReader(self.paths.chat_inbox)\n        self.ai = LocalAIResponder()\n\n        self.stop_event = threading.Event()\n        self.queue: \"queue.Queue[str]\" = queue.Queue()\n        self.threads: List[threading.Thread] = []\n\n        self.started_at = dt.datetime.now(dt.timezone.utc)\n        self.last_command_at: Optional[str] = None\n        
self.last_rollup_at: Optional[str] = None\n        self.command_count = 0\n        self.last_reply = \"\"\n        self.seen_times: Dict[str, float] = {}\n\n        self.system_instructions = textwrap.dedent(\"\"\"\n            You are HexWatch, a concise local operator assistant.\n            You help monitor a contained runtime.\n            Answer directly and briefly.\n            Never claim actions you did not actually take.\n            Never request arbitrary shell execution.\n        \"\"\").strip()\n\n    def now(self) -> str:\n        return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec=\"seconds\")\n\n    def uptime(self) -> int:\n        return int((dt.datetime.now(dt.timezone.utc) - self.started_at).total_seconds())\n\n    def goal_text(self) -> str:\n        try:\n            return self.paths.goal_txt.read_text(encoding=\"utf-8\").strip()\n        except Exception:\n            return \"\"\n\n    def read_autonomy_state(self) -> Dict[str, Any]:\n        try:\n            return json.loads(self.paths.autonomy_json.read_text(encoding=\"utf-8\"))\n        except Exception:\n            return {\"enabled\": False, \"last_tick\": None}\n\n    def write_autonomy_state(self, enabled: bool) -> None:\n        AtomicFile.write_json(self.paths.autonomy_json, {\"enabled\": enabled, \"last_tick\": self.now()})\n\n    def write_state(self) -> None:\n        AtomicFile.write_json(self.paths.state_json, {\n            \"app\": APP_NAME,\n            \"version\": VERSION,\n            \"pid\": os.getpid(),\n            \"root\": str(self.paths.root),\n            \"started_at\": self.started_at.astimezone().isoformat(timespec=\"seconds\"),\n            \"uptime_seconds\": self.uptime(),\n            \"last_command_at\": self.last_command_at,\n            \"last_rollup_at\": self.last_rollup_at,\n            \"command_count\": self.command_count,\n            \"ai_available\": self.ai.available(),\n        })\n        AtomicFile.write_json(self.paths.heartbeat_json, {\n            \"ts\": self.now(),\n            \"pid\": os.getpid(),\n            \"uptime_seconds\": self.uptime(),\n            \"ok\": True,\n        })\n\n    def append_command_record(self, raw: str, response: str, ok: bool) -> None:\n        rec = {\n            \"ts\": self.now(),\n            \"raw\": raw,\n            \"ok\": ok,\n            \"response_preview\": response[:500],\n        }\n        with self.paths.commands_jsonl.open(\"a\", encoding=\"utf-8\") as fh:\n            fh.write(json.dumps(rec, sort_keys=True) + \"\\n\")\n\n    def reply(self, msg: str) -> None:\n        clean = msg.rstrip() + \"\\n\"\n        with self.paths.chat_outbox.open(\"a\", encoding=\"utf-8\") as fh:\n            fh.write(clean + \"\\n\")\n        AtomicFile.write_text(self.paths.last_reply_txt, clean)\n        self.last_reply = clean\n        self.log.chat(\"out\", clean.strip())\n        self.log.info(f\"reply sent ({len(clean)} bytes)\")\n\n    def format_status(self) -> str:\n        auto = self.read_autonomy_state()\n        return textwrap.dedent(f\"\"\"\n            [{APP_NAME} {VERSION}]\n            ts: {self.now()}\n            pid: {os.getpid()}\n            root: {self.paths.root}\n            uptime_seconds: {self.uptime()}\n            last_command_at: {self.last_command_at or 'none'}\n            last_rollup_at: {self.last_rollup_at or 'none'}\n            command_count: {self.command_count}\n            ai_available: {self.ai.available()}\n            autonomy_enabled: {auto.get('enabled', False)}\n            goal: {self.goal_text() or '(none)'}\n            inbox: {self.paths.chat_inbox}\n            outbox: {self.paths.chat_outbox}\n\n            ---- main log tail ----\n            {tail_file(self.paths.main_log, 8) or '(empty)'}\n        \"\"\").strip()\n\n    def generate_rollup(self) -> str:\n        text = textwrap.dedent(f\"\"\"\n            HEXWATCH V6 ROLLUP\n            generated: {self.now()}\n            pid: {os.getpid()}\n            uptime_seconds: {self.uptime()}\n            commands_processed: {self.command_
count}\n            last_command_at: {self.last_command_at or 'none'}\n            last_rollup_at: {self.last_rollup_at or 'none'}\n            ai_available: {self.ai.available()}\n            autonomy_enabled: {self.read_autonomy_state().get('enabled', False)}\n            goal: {self.goal_text() or '(none)'}\n\n            == MAIN LOG TAIL ==\n            {tail_file(self.paths.main_log, 20) or '(empty)'}\n\n            == ERROR LOG TAIL ==\n            {tail_file(self.paths.error_log, 20) or '(empty)'}\n\n            == CHAT HISTORY TAIL ==\n            {tail_file(self.paths.chat_history, 20) or '(empty)'}\n        \"\"\").strip() + \"\\n\"\n        AtomicFile.write_text(self.paths.rollup_txt, text)\n        AtomicFile.write_text(self.paths.status_txt, self.format_status() + \"\\n\")\n        self.last_rollup_at = self.now()\n        return text\n\n    def ai_reply(self, text: str) -> str:\n        if not self.ai.available():\n            return \"local AI is unavailable; install Ollama and make sure llama3 is pulled\"\n        prompt = textwrap.dedent(f\"\"\"\n            Current status snapshot:\n            {self.format_status()}\n\n            User message:\n            {text}\n        \"\"\").strip()\n        return self.ai.reply(self.system_instructions, prompt)\n\n    def approved_tail(self, rel_path: str, lines: int = 80) -> str:\n        rel = rel_path.strip().lstrip(\"/\")\n        if rel not in APPROVED_TAIL_TARGETS:\n            return f\"tail target not approved: {rel}\"\n        target = (self.paths.root / rel).resolve()\n        return f\"== tail {target} ({lines}) ==\\n\" + tail_file(target, lines)\n\n    def perform_ai_action(self, action: Dict[str, Any]) -> str:\n        kind = str(action.get(\"type\", \"reply\")).strip().lower()\n        if kind == \"reply\":\n            return str(action.get(\"message\", \"\")).strip() or \"(empty reply)\"\n        if kind == \"status\":\n            return self.format_status()\n        if kind == \"rollup\":\n            return self.generate_rollup().strip()\n        if kind == \"note\":\n            msg = str(action.get(\"message\", \"\")).strip()\n            self.log.info(f\"NOTE {msg}\")\n            return f\"noted: {msg}\" if msg else \"note action missing message\"\n        if kind == \"tail\":\n            return self.approved_tail(str(action.get(\"path\", \"\")).strip(), int(action.get(\"lines\", 80)))\n        return f\"unapproved action: {kind}\"\n\n    def ai_decide_action(self, message: str) -> str:\n        if not self.ai.available():\n            return \"local AI is unavailable; install Ollama and make sure llama3 is pulled\"\n        schema = textwrap.dedent(\"\"\"\n            You are HexWatch.\n            Return a JSON object only.\n            Choose one action from this whitelist:\n            - {\"type\":\"reply\",\"message\":\"...\"}\n            - {\"type\":\"status\"}\n            - {\"type\":\"rollup\"}\n            - {\"type\":\"note\",\"message\":\"...\"}\n            - {\"type\":\"tail\",\"path\":\"logs/main.log\",\"lines\":80}\n            Approved tail paths:\n            logs/main.log, logs/error.log, logs/chat_history.log, reports/status.txt, reports/rollup.txt, state/state.json, state/heartbeat.json\n            Never choose run or arbitrary shell execution.\n            Keep the action useful and concise.\n        \"\"\").strip()\n        payload = textwrap.dedent(f\"\"\"\n            Status snapshot:\n            {self.format_status()}\n\n            Message:\n            {message}\n        \"\"\").strip()\n        return self.perform_ai_action(self.ai.decide(schema, payload))\n\n    def handle_help(self) -> str:\n        return textwrap.dedent(\"\"\"\n            commands:\n              help\n              status\n              ping\n              rollup\n              note <text>\n              goal <text>\n              autonomy on\n              autonomy off\n              ask <text>\n              tail <path> [n]\n              run <shell command>\n              restart\n              stop\n        \"\"\").strip()\n\n    
def handle_run(self, args: List[str]) -> str:\n        if not args:\n            return \"error: usage: run <shell command>\"\n        command = \" \".join(args)\n        try:\n            r = subprocess.run(\n                command,\n                shell=True,\n                text=True,\n                capture_output=True,\n                timeout=20,\n                cwd=str(self.paths.root),\n                executable=\"/bin/bash\",\n            )\n            stdout = r.stdout or \"\"\n            stderr = r.stderr or \"\"\n            return textwrap.dedent(f\"\"\"\n                $ {command}\n                exit_code: {r.returncode}\n\n                [stdout]\n                {stdout.strip() or '(empty)'}\n\n                [stderr]\n                {stderr.strip() or '(empty)'}\n            \"\"\").strip()\n        except subprocess.TimeoutExpired:\n            return \"command timed out after 20s\"\n\n    def dispatch(self, raw: str) -> str:\n        try:\n            parts = shlex.split(raw)\n        except ValueError:\n            return self.ai_decide_action(raw)\n\n        if not parts:\n            return \"\"\n\n        cmd = parts[0].lower()\n        args = parts[1:]\n\n        if cmd == \"help\":\n            return self.handle_help()\n        if cmd == \"status\":\n            return self.format_status()\n        if cmd == \"ping\":\n            return f\"pong {self.now()}\"\n        if cmd == \"rollup\":\n            return self.generate_rollup().strip()\n        if cmd == \"note\":\n            msg = \" \".join(args).strip()\n            if not msg:\n                return \"error: usage: note <text>\"\n            self.log.info(f\"NOTE {msg}\")\n            return f\"noted: {msg}\"\n        if cmd == \"goal\":\n            msg = \" \".join(args).strip()\n            if not msg:\n                return \"error: usage: goal <text>\"\n            AtomicFile.write_text(self.paths.goal_txt, msg + \"\\n\")\n            return f\"goal set: {msg}\"\n        if cmd == \"autonomy\":\n            if not args or args[0].lower() not in {\"on\", \"off\"}:\n                return \"error: usage: autonomy on|off\"\n            enabled = args[0].lower() == \"on\"\n            self.write_autonomy_state(enabled)\n            return f\"autonomy {'enabled' if enabled else 'disabled'}\"\n        if cmd == \"ask\":\n            return self.ai_reply(\" \".join(args).strip())\n        if cmd == \"tail\":\n            if not args:\n                return \"error: usage: tail <path> [n]\"\n            path = args[0]\n            lines = int(args[1]) if len(args) > 1 else 40\n            return self.approved_tail(path, lines)\n        if cmd == \"run\":\n            return self.handle_run(args)\n        if cmd == \"restart\":\n            self.reply(\"restart requested; stopping current process\")\n            self.stop_event.set()\n            return \"restart requested\"\n        if cmd == \"stop\":\n            self.reply(\"stop requested; shutting down\")\n            self.stop_event.set()\n            return \"stop requested\"\n\n        return self.ai_decide_action(raw)\n\n    def inbox_loop(self) -> None:\n        self.log.info(\"inbox loop started\")\n        while not self.stop_event.is_set():\n            try:\n                for line in self.inbox.read_new_lines():\n                    self.log.chat(\"in\", line)\n                    self.queue.put(line)\n                time.sleep(1.0)\n            except Exception as e:\n                self.log.error(f\"inbox loop failure: {e}\")\n                time.sleep(1.0)\n        self.log.info(\"inbox loop stopped\")\n\n    def command_loop(self) -> None:\n        self.log.info(\"command loop started\")\n        while not self.stop_event.is_set():\n            try:\n                try:\n                    raw = self.queue.get(timeout=0.5)\n                except queue.Empty:\n                    continue\n\n                h = hashlib.sha256(raw.encode()).hexdigest()\n                now = time.time()\n                if now - self.seen_times.get(h, 0.0) < DEDUP_
WINDOW_SECONDS:\n                    self.log.info(f\"duplicate command skipped: {raw}\")\n                    continue\n                self.seen_times[h] = now\n\n                self.command_count += 1\n                self.last_command_at = self.now()\n                ok = True\n                try:\n                    response = self.dispatch(raw)\n                except Exception as e:\n                    ok = False\n                    response = f\"unhandled error: {e}\"\n                    self.log.error(f\"command failure for {raw!r}: {e}\")\n\n                if response:\n                    self.reply(response)\n                self.append_command_record(raw, response, ok)\n                self.write_state()\n            except Exception as e:\n                self.log.error(f\"command loop failure: {e}\")\n        self.log.info(\"command loop stopped\")\n\n    def heartbeat_loop(self) -> None:\n        self.log.info(\"heartbeat loop started\")\n        while not self.stop_event.is_set():\n            try:\n                self.write_state()\n                AtomicFile.write_text(self.paths.status_txt, self.format_status() + \"\\n\")\n            except Exception as e:\n                self.log.error(f\"heartbeat loop failure: {e}\")\n            self.stop_event.wait(5.0)\n        self.log.info(\"heartbeat loop stopped\")\n\n    def rollup_loop(self) -> None:\n        self.log.info(\"rollup loop started\")\n        while not self.stop_event.is_set():\n            try:\n                self.generate_rollup()\n            except Exception as e:\n                self.log.error(f\"rollup loop failure: {e}\")\n            self.stop_event.wait(20.0)\n        self.log.info(\"rollup loop stopped\")\n\n    def autonomy_loop(self) -> None:\n        self.log.info(\"autonomy loop started\")\n        while not self.stop_event.is_set():\n            try:\n                auto = self.read_autonomy_state()\n                goal = self.goal_text()\n                if not self.ai.available() or not auto.get(\"enabled\") or not goal:\n                    self.stop_event.wait(30.0)\n                    continue\n\n                payload = textwrap.dedent(f\"\"\"\n                    Goal:\n                    {goal}\n\n                    Current status:\n                    {self.format_status()}\n\n                    Recent chat history:\n                    {tail_file(self.paths.chat_history, 20) or '(empty)'}\n\n                    Recent errors:\n                    {tail_file(self.paths.error_log, 10) or '(empty)'}\n                \"\"\").strip()\n\n                decision = self.ai.decide(textwrap.dedent(\"\"\"\n                    You are HexWatch autonomous mode.\n                    Return a JSON object only.\n                    Choose one action from:\n                    - {\"type\":\"reply\",\"message\":\"...\"}\n                    - {\"type\":\"status\"}\n                    - {\"type\":\"rollup\"}\n                    - {\"type\":\"note\",\"message\":\"...\"}\n                    - {\"type\":\"tail\",\"path\":\"logs/main.log\",\"lines\":80}\n                    - {\"type\":\"reply\",\"message\":\"\"}\n                    Never request raw shell commands.\n                    Only send a message when something useful changed, or a short proactive update helps.\n                \"\"\").strip(), payload)\n\n                output = self.perform_ai_action(decision)\n                if output and output.strip() and output.strip() != \"(empty reply)\":\n                    self.reply(output)\n                self.write_autonomy_state(True)\n                self.write_state()\n            except Exception as e:\n                self.log.error(f\"autonomy loop failure: {e}\")\n            self.stop_event.wait(30.0)\n        self.log.info(\"autonomy loop stopped\")\n\n    def install_signal_handlers(self) -> None:\n        def handler(signum: int, _frame: Any) -> None:\n            self.log.info(f\"signal received: {signum}\")\n            self.stop_event.set()\n        signal.signal(signal.SIGINT, handler)\n    
    signal.signal(signal.SIGTERM, handler)\n\n    def bootstrap_files(self) -> None:\n        run_sh = textwrap.dedent(\"\"\"\\\n            #!/usr/bin/env bash\n            set -euo pipefail\n            ROOT=\"${HOME}/hexwatch_v6\"\n            exec python3 \"$ROOT/hexwatch_v6_monolith.py\" --root \"$ROOT\" --foreground\n        \"\"\")\n        talk_sh = textwrap.dedent(\"\"\"\\\n            #!/usr/bin/env bash\n            set -euo pipefail\n            ROOT=\"${HOME}/hexwatch_v6\"\n            OUT=\"$ROOT/run/chat.outbox\"\n            IN=\"$ROOT/run/chat.inbox\"\n            MSG=\"${*:-status}\"\n\n            mkdir -p \"$ROOT/run\"\n            touch \"$OUT\" \"$IN\"\n\n            before=$(wc -l < \"$OUT\" 2>/dev/null || echo 0)\n            printf '%s\\n' \"$MSG\" >> \"$IN\"\n            echo \"[sent] $MSG\"\n            sleep 2\n            after=$(wc -l < \"$OUT\" 2>/dev/null || echo 0)\n\n            if [ \"$after\" -gt \"$before\" ]; then\n              sed -n \"$((before+1)),$((after))p\" \"$OUT\"\n            else\n              echo \"[no new reply yet]\"\n            fi\n        \"\"\")\n        AtomicFile.write_text(self.paths.bin / \"run.sh\", run_sh)\n        AtomicFile.write_text(self.paths.bin / \"talk.sh\", talk_sh)\n        os.chmod(self.paths.bin / \"run.sh\", 0o755)\n        os.chmod(self.paths.bin / \"talk.sh\", 0o755)\n\n        if not self.paths.autonomy_json.exists():\n            self.write_autonomy_state(False)\n        if not self.goal_text():\n            AtomicFile.write_text(\n                self.paths.goal_txt,\n                \"watch system health and respond when something important changes\\n\",\n            )\n\n    def run(self) -> int:\n        self.instance.acquire()\n        self.install_signal_handlers()\n        self.bootstrap_files()\n        self.write_state()\n        self.generate_rollup()\n        self.log.info(f\"{APP_NAME} {VERSION} starting pid={os.getpid()} root={self.paths.root}\")\n        self.reply(f\"{APP_NAME} {VERSION} online at {self.now()}\")\n\n        for name, fn in [\n            (\"inbox\", self.inbox_loop),\n            (\"commands\", self.command_loop),\n            (\"heartbeat\", self.heartbeat_loop),\n            (\"rollup\", self.rollup_loop),\n            (\"autonomy\", self.autonomy_loop),\n        ]:\n            t = threading.Thread(target=fn, name=name, daemon=True)\n            t.start()\n            self.threads.append(t)\n\n        try:\n            while not self.stop_event.is_set():\n                time.sleep(0.5)\n        finally:\n            self.log.info(\"shutdown sequence starting\")\n            self.stop_event.set()\n            deadline = time.time() + 3\n            for t in self.threads:\n                t.join(timeout=max(0.0, deadline - time.time()))\n            try:\n                self.write_state()\n                self.generate_rollup()\n            except Exception as e:\n                self.log.error(f\"shutdown write failure: {e}\")\n            self.instance.release()\n            self.log.info(\"shutdown complete\")\n        return 0\n\ndef main() -> int:\n    ap = argparse.ArgumentParser()\n    ap.add_argument(\"--root\", default=\"~/hexwatch_v6\")\n    ap.add_argument(\"--foreground\", action=\"store_true\", default=True)\n    args = ap.parse_args()\n    return Monolith(Path(args.root)).run()\n\nif __name__ == \"__main__\":\n    sys.exit(main())"}]}
																																																					```
																																																					

# HEXWATCH V6 — LOCAL AUTONOMOUS AGENT

How to use: Operator workflow is basically locked in:
(bash commands below to start system and agent)
~/hexwatch_v6/bin/launch.sh
~/hexwatch_v6/bin/menu.sh
~/hexwatch_v6/bin/watch.sh
~/hexwatch_v6/bin/talk.sh status
~/hexwatch_v6/bin/talk.sh metrics
~/hexwatch_v6/bin/talk.sh "report anomaly"

## Overview

Hexwatch v6 is a fully local, self-contained AI agent runtime.

It combines:

* a command interface (`talk.sh`)
* a persistent agent loop (`hexwatch_v6_monolith.py`)
* local AI via Ollama (`phi3:mini`)
* memory, metrics, and audit logging
* anomaly detection and reporting
* an operator dashboard and control scripts

Everything runs locally. No network services required.

---

## Directory Layout

```
hexwatch_v6/
├── bin/            # operator commands
├── logs/           # runtime logs
├── run/            # inbox/outbox + lock
├── state/          # memory + metrics + config
├── reports/        # status + reports
├── tmp/            # backups + snapshots
├── archive/        # old backups
└── hexwatch_v6_monolith.py
```

---

## Core Concepts

### 1. Agent Loop

The monolith runs continuously and:

* reads commands from `run/chat.inbox`
* writes responses to `run/chat.outbox`
* updates logs, metrics, and reports
* optionally runs autonomous decisions

---

### 2. Command System

All commands go through:

```
bin/talk.sh
```

Examples:

```
talk.sh ping
talk.sh status
talk.sh metrics
talk.sh "ask say hello"
talk.sh "report anomaly"
talk.sh "goal watch logs"
```

---

### 3. Autonomy

Autonomy is optional and controlled by:

```
talk.sh "autonomy on"
talk.sh "autonomy off"
```

When enabled, the agent:

* reads goal from `state/goal.txt`
* evaluates conditions
* logs decisions to `logs/audit.log`
* produces notes or replies

---

## Operator Commands

### Start / Stop

```
bin/launch.sh     # start system
bin/stop.sh       # stop system
```

---

### Menu (interactive)

```
bin/menu.sh
```

Options:

1. launch
2. stop
3. status
4. metrics
5. anomaly report
6. dashboard
7. backup
8. incident report

---

### Dashboard (live view)

```
bin/watch.sh
```

Shows:

* goal
* status
* metrics
* memory
* daily report
* audit tail
* errors

---

### Backup

```
bin/backup.sh
```

Creates snapshot in:

```
tmp/backup_<timestamp>/
```

---

### Incident Report

```
bin/incident_report.sh
```

Writes:

```
reports/incidents.txt
```

---

## Reports

### Status

```
reports/status.txt
```

### Daily Report

```
talk.sh "report daily"
```

Includes:

* uptime
* commands
* AI usage
* anomaly score

---

### Anomaly Report

```
talk.sh "report anomaly"
```

Returns JSON:

* score
* reasons
* audit snapshot
* error snapshot

---

## State Files

```
state/
├── goal.txt
├── memory.json
├── metrics.json
├── autonomy.json
```

### Set goal

```
talk.sh "goal watch logs for anomalies"
```

### Memory

```
talk.sh "memory set key value"
talk.sh "memory get key"
```

---

## Logs

```
logs/
├── audit.log      # actions + decisions
├── main.log       # runtime events
├── error.log      # errors
├── nohup.log      # daemon output
```

---

## How It Works

### Data Flow

```
talk.sh → inbox → monolith → outbox → talk.sh
```

### UI Flow

```
watch.sh → reads reports + logs → displays dashboard
```

### Autonomy Flow

```
goal → decision engine → audit log → optional reply
```

---

## Typical Workflow

### Start system

```
bin/launch.sh
```

### Monitor

```
bin/watch.sh
```

### Send commands

```
bin/talk.sh status
bin/talk.sh metrics
```

### Enable autonomy

```
bin/talk.sh "autonomy on"
```

---

## Safety Model

* no direct shell execution by agent
* bounded autonomy decisions
* anomaly scoring
* backoff on failures
* lockfile prevents duplicate processes

---

## Troubleshooting

### No response

```
bin/talk.sh status
```

### Restart system

```
bin/stop.sh
bin/launch.sh
```

### Check logs

```
tail -n 50 logs/error.log
tail -n 50 logs/audit.log
```

---

## Version

```
talk.sh version
```

---

## Self Test

```
talk.sh selftest
```

Returns system health checks.

---

## Final Notes

Hexwatch v6 is:

* local-first
* file-driven
* loop-based
* observable
* controllable

It is designed to be simple, stable, and extensible.

Operate it like a service, not a script.

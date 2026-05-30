# Jarvis

Jarvis is the local-first assistant shell and control plane for a supervised personal AI assistant. Current product direction: Jarvis Lite, a voice-first AI operator and interview coach that runs on your laptop, uses explicit approvals for risky actions, and keeps runs, memory, and traces local by default.

## Repo Role

This repo is the Jarvis runtime: desktop shell, CLI, orchestration, approvals, memory, and voice workflow handling.

OMNIRA is intentionally separate. It can stay in your external `Project OM` folder and connect to Jarvis later through the backend adapter when its endpoint is ready.

For stability, the internal Python package and CLI command still use the existing `agenthub` name for now.

## What We Are Building Now

Jarvis Lite is the first focused product on top of Agent Hub. It is intended to be a legitimate AI-assisted tool for:

- voice-driven task execution on your own machine
- project assistance across coding, docs, research, and repo operations
- interview practice, answer coaching, and post-session feedback
- personal workflow automation with approvals, logs, and memory

The target v1 is not an unrestricted system controller. It is a supervised assistant with bounded tools, auditability, and separate personal/work profiles.

## Voice-Centric Product Rule

Jarvis should be voice-centric at the product surface.

- voice is the primary command path
- visuals exist to show state, feedback, approvals, progress, and results
- backend workflows may search, inspect, download, manage desktop actions, and recover from failures, but the assistant should still feel like a spoken operator rather than a text console
- typing remains available only as a fallback channel when speech is not practical

## Product Direction

Jarvis Lite is planned as five layers:

1. Voice and session capture
2. Intent routing and agent orchestration
3. Tool execution with permission gates
4. Coaching and feedback workflows
5. Memory, tracing, and review

See `docs/JARVIS_LITE_MVP.md` and `docs/ROADMAP.md` for the concrete MVP shape.

## Quick start

1. Create a virtual environment and install:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e .
```

2. Set your key:

```bash
setx OPENAI_API_KEY "your-key-here"
```

3. Run a task:

```bash
agenthub run "Update README with setup steps" --agent docs
```

## Setup Guide

### Prerequisites
- Python 3.10+
- An OpenAI API key

Optional for live microphone capture:

```bash
pip install -e .[voice]
```

Optional for the cinematic desktop shell:

```bash
pip install -e .[desktop]
```

### 1) Create and activate a virtual environment
```bash
python -m venv .venv
# macOS/Linux
. .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

### 2) Install the project
```bash
pip install -e .
```

### 3) Configure environment variables
Copy `.env.example` or set directly in your shell:

```bash
# macOS/Linux
export OPENAI_API_KEY="your-key-here"

# Windows PowerShell (current session)
$env:OPENAI_API_KEY="your-key-here"
```

Note: `setx` only applies to new terminal sessions.

### 4) Run a quick test
```bash
agenthub list-agents
```

### 5) Run a task
```bash
agenthub run "Update README with setup steps" --agent docs
```

### Notes
- Default model: `gpt-5.2-codex`
- Runs and memory are stored under `data/` (not written into your project folders).

## Commands

- `agenthub list-agents`
- `agenthub evals --file evals/golden_tasks.json`
- `agenthub list-tools`
- `agenthub list-profiles`
- `agenthub show-profile personal`
- `agenthub check-tool-policy personal shell`
- `agenthub check-path-policy personal C:/Users/you/Documents`
- `agenthub check-app-policy work code`
- `agenthub check-command-policy personal "git status"`
- `agenthub check-recording-policy personal`
- `agenthub audit-log "open terminal" personal terminal success --detail "manual test"`
- `agenthub audit-history --limit 10`
- `agenthub voice-route "plan a repo cleanup and update docs"`
- `agenthub listen-on --mode push-to-talk`
- `agenthub listen-status`
- `agenthub listen-off`
- `agenthub list-stt-providers`
- `agenthub transcribe-text "update the project roadmap"`
- `agenthub mic-config --device default --sample-rate 16000 --chunk-ms 250 --mode push-to-talk`
- `agenthub mic-status`
- `agenthub mic-devices`
- `agenthub mic-record --duration 5 --out data/voice/sample.wav`
- `agenthub capture-start --provider text`
- `agenthub capture-stop`
- `agenthub interview-start "Backend practice"`
- `agenthub interview-add-turn <session-id> interviewer "Tell me about a time you handled production pressure"`
- `agenthub interview-capture-turn <session-id> interviewer --text "Tell me about a time you handled production pressure"`
- `agenthub interview-capture-turn <session-id> candidate --text "I stabilized the incident, coordinated rollback, and reduced recovery time"`
- `agenthub interview-summary <session-id>`
- `agenthub interview-show <session-id>`
- `agenthub interview-coach <session-id>`
- `agenthub interview-drills --limit 10`
- `agenthub run "task" --agent coder`
- `agenthub run "task" --agent auto`
- `agenthub plan "task"`
- `agenthub run-plan "task"`
- `agenthub enqueue "task" --agent auto`
- `agenthub worker --once`
- `agenthub queue-status`
- `agenthub web --host 127.0.0.1 --port 8000`
- `agenthub desktop`
- `agenthub desktop-cinematic`
- `agenthub backend-check`
- `agenthub export-dataset --out data/finetune.jsonl`
- `agenthub repo-health`
- `agenthub propose-fix "task"`
- `agenthub apply-proposal <id> --confirm`
- `agenthub auto-apply-docs <id>`
- `agenthub record-approval <id> --note "why approved"`
- `agenthub schedule-repo-health --interval 3600`
- `agenthub maintenance --interval 3600 --cleanup-days 7`

## Streaming

The web UI uses streaming responses when the backend supports it. If streaming fails, it falls back to non-streaming chat.

## Tracing

When `tracing.enabled` is true (see `config.yaml`), each run emits JSONL spans under `data/traces/<project-id>/<trace-id>.jsonl`. This captures router handoffs, OpenAI calls, and run persistence without affecting core flow.

## Data

Runs and project memory are stored under `data/` and are not written into your project folders.

## Local Model Backend (Path A)

If you run your own OpenAI-compatible server (e.g., vLLM), set:

```yaml
# config.yaml
backend: local
base_url: "http://127.0.0.1:8000/v1"
api_key_env: OPENAI_API_KEY
```

Then set `OPENAI_API_KEY` to any value your local server expects (some accept any string).

## OMNIRA Backend (Path B)

Jarvis can connect to OMNIRA directly through the shared backend adapter. For the current OMNIRA API, set:

```yaml
# config.yaml
backend: omnira
base_url: "http://127.0.0.1:8000"
model: "omnira-lite-qwen-3b-v0.1"
api_key_env: OPENAI_API_KEY
```

Jarvis will call OMNIRA `/models` for backend checks and OMNIRA `/chat` for task execution. Agent names such as `coder`, `infra`, `research`, and `security` are mapped to OMNIRA model families automatically.

OMNIRA does not need to be moved into this repo. Jarvis can point to an OMNIRA service even if OMNIRA continues to live in a separate folder or separate project lifecycle.

See `docs/LOCAL_MODEL_AZURE.md` and `config.local.example.yaml` for a full Azure setup example.

## Model Registry

Use `models.yaml` to set a default model and per-agent overrides (used when `backend: local`). If an agent profile sets `model`, it takes precedence.

## Current Focus

The current product direction is Jarvis Lite: a supervised personal AI assistant built on top of Agent Hub. The immediate focus is:

- stabilizing the existing platform primitives
- adding voice-driven and approval-based workflows
- building a legitimate interview coaching flow
- keeping data, memory, and action history local-first by default

See `docs/JARVIS_LITE_MVP.md`, `docs/ROADMAP.md`, and `docs/PLATFORM_INVENTORY.md` for the active execution view.

## Cinematic Desktop Shell

The repo now includes an experimental `PySide6 + QML` desktop path alongside the Tkinter prototype.

Run it with:

```bash
agenthub desktop-cinematic
```

The current Qt shell is the first migration slice. It reuses the existing Jarvis Python core for backend checks, routing, streaming, and listen-state integration while beginning the move toward a more cinematic desktop experience.

Voice-first operating target:

- speak requests naturally instead of navigating text-heavy controls
- let Jarvis search repos, search the web, inspect the desktop, download artifacts, and help recover from errors through backend workflows
- keep visual feedback focused on state, approvals, results, and progress instead of requiring keyboard-driven interaction

See `docs/VOICE_CENTRIC_OPERATING_MODEL.md` for the product rule and capability model.

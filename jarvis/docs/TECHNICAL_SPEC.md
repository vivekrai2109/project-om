# Technical Specification

## Services
- Web UI + API: FastAPI app in `agenthub/web.py`.
- Orchestrator: `agenthub/orchestrator.py`.
- Queue worker: `agenthub/queue.py`.
- CLI: Typer app in `agenthub/cli.py`.
- Current desktop shell: Tkinter prototype in `agenthub/desktop.py`.
- Experimental cinematic desktop shell: Qt/QML path in `agenthub/desktop_qt.py` and `agenthub/qml/Main.qml`.

## Storage
- `data/runs/`: JSON run logs.
- `data/memory/`: project memory summaries.
- `data/queue/`: pending/processing/done/failed tasks.
- `data/proposals/`: proposal summaries, raw outputs, and patches.
- `data/traces/`: JSONL traces for agent execution and handoffs.
- `data/audit/`: user-visible action audit events.
- `data/voice/`: local listen-state and future voice session artifacts.
- `data/interviews/`: local interview coaching sessions and transcript turns.

## Config
- `config.yaml`: backend, model, timeouts, retries.
- `models.yaml`: per-agent model overrides.
- `profiles.yaml`: user policy profiles for personal/work boundaries.
- optional dependency group `voice`: live microphone capture via `sounddevice`.
- optional dependency group `desktop`: cinematic desktop shell via `PySide6`.

## API Endpoints (local)
- `GET /` Web UI
- `POST /chat` Chat API
- `POST /chat/stream` Streaming chat (SSE)
- `GET /run?file=...` Run details
- `GET /run/download?file=...` Download run JSON
- `POST /proposal/check` Docs-only patch check
- `POST /proposal/check-general` General patch check
- `POST /proposal/apply` Auto-apply docs
- `POST /proposal/apply-manual` Apply patch with confirmation
- `POST /proposal/approve` Record approval

## CLI Commands
- `agenthub list-agents`
- `agenthub evals`
- `agenthub list-tools`
- `agenthub list-profiles`, `agenthub show-profile`
- `agenthub check-tool-policy`
- `agenthub check-path-policy`, `agenthub check-app-policy`
- `agenthub check-command-policy`, `agenthub check-recording-policy`
- `agenthub audit-log`, `agenthub audit-history`
- `agenthub voice-route`, `agenthub listen-on`, `agenthub listen-status`, `agenthub listen-off`
- `agenthub list-stt-providers`, `agenthub transcribe-text`, `agenthub transcribe-file`
- `agenthub mic-config`, `agenthub mic-status`, `agenthub mic-devices`, `agenthub mic-record`
- `agenthub capture-start`, `agenthub capture-stop`
- `agenthub interview-start`, `agenthub interview-add-turn`, `agenthub interview-summary`
- `agenthub interview-capture-turn`
- `agenthub interview-show`, `agenthub interview-list`, `agenthub interview-coach`, `agenthub interview-drills`
- `agenthub run`, `agenthub plan`, `agenthub run-plan`
- `agenthub enqueue`, `agenthub worker`, `agenthub queue-status`
- `agenthub web`, `agenthub desktop`, `agenthub desktop-cinematic`, `agenthub backend-check`
- `agenthub export-dataset`, `agenthub repo-health`
- `agenthub propose-fix`, `agenthub apply-proposal`
- `agenthub auto-apply-docs`, `agenthub record-approval`
- `agenthub schedule-repo-health`, `agenthub maintenance`

## Current Product Direction
- Platform role: Jarvis control plane and assistant shell
- Primary product workflows: voice-driven operator tasks, project assistance, and consent-based interview coaching
- Safety model: explicit approvals for risky actions, auditable runs, local-first storage
- Naming split: repo/folder identity is Jarvis, while the internal Python package and CLI remain `agenthub` until a later controlled rename

## Voice-Centric Operating Model
- Jarvis is voice-primary at the desktop surface.
- Speech is the default command path; typing is a fallback channel.
- The UI should favor microphone state, listen state, spoken command capture, approval prompts, result summaries, and progress visuals over text-heavy controls.
- Backend workflows remain capable of repo search, web search, downloads, desktop actions, file operations, and error recovery, but those capabilities should present through a spoken assistant experience rather than a traditional tooling dashboard.
- The cinematic desktop should progressively hide low-value manual controls once the voice path is reliable enough for daily use.

## Desktop UI Direction
- The current Tkinter shell is a functional prototype only. It is suitable for control panels and basic live status, but it is not the long-term rendering layer for a cinematic Jarvis experience.
- Recommended primary path: `PySide6 + QML` for the production desktop shell.
- Recommended fallback/high-ceiling alternative: `Tauri + React` with Canvas/WebGL for a heavier visual stack.
- Decision rationale: Jarvis already has a working Python core, so `PySide6 + QML` keeps voice, orchestration, OMNIRA backend routing, memory, and local tooling in the same runtime while materially upgrading animation, compositing, transitions, and scene control.
- Architectural boundary: the desktop shell should become a thin presentation layer over the existing Python control plane rather than absorbing orchestration logic.

## Cinematic UI Requirements
- full-screen scene composition instead of admin-style panels
- layered motion states for idle, listening, thinking, speaking, and warning
- animated voice visualizers driven by live microphone state
- glass, glow, depth, and scan-line effects that require stronger rendering than Tkinter provides
- state-driven transitions between conversation, approval, session review, and system status surfaces
- future support for a central animated assistant core instead of static box layout

## Desktop Migration Shape
- Phase 1: keep `agenthub/desktop.py` as the working prototype for local testing
- Phase 2: extract a stable desktop-facing service boundary for conversation send, stream, session load, backend status, microphone state, and voice controls
- Phase 3: build a new `PySide6 + QML` shell against that boundary
- Phase 4: retire the Tkinter shell after feature parity for voice, sessions, streaming, and approvals
- Phase 5: evaluate whether a later `Tauri + React/WebGL` shell is justified for even richer cinematic rendering

## Current Cinematic Shell Slice
- `agenthub desktop-cinematic` starts the first `PySide6 + QML` shell.
- The current Qt bridge reuses existing backend checks, router-based agent selection, streaming responses, microphone status, and listen-state persistence.
- The current QML scene now includes voice capture controls, live listen state, session sync, pending approvals, and approval history, but it still needs further reduction of text-first interaction to fully meet the voice-centric target.

## Policy Model
- user profile boundaries are defined in `profiles.yaml`
- tool metadata and baseline risk are defined in `tools/registry.yaml`
- approval decisions can be evaluated locally from profile policy plus tool risk

## Voice Layer Foundation
- `agenthub/voice.py` handles transcript routing and listen-state persistence
- `agenthub/speech.py` provides STT provider abstraction, microphone config, and capture-state persistence
- current local provider paths are `text` and `windows_dictation`; remote audio transcription is scaffolded through `openai_audio`
- live microphone capture is available through optional `sounddevice` support and records WAV clips locally

## Interview Coaching Foundation
- `agenthub/interview.py` stores local interview sessions and transcript turns
- interviewer turns are classified with lightweight heuristics for question type
- session summaries and lightweight answer scoring can be generated locally before deeper coaching is added
- recurring coaching themes can be aggregated into drill suggestions across sessions
- `interview-capture-turn` bridges speech input and interview session storage in one command

## Model Backends
- `openai`: OpenAI API client.
- `local`: OpenAI-compatible server (vLLM).
- `omnira`: reserved backend mode for the user's OMNIRA assistant model, routed through the shared backend adapter.

## OMNIRA Integration Contract
- The runtime backend selection is centralized in `agenthub/backend_client.py`.
- `agenthub/orchestrator.py`, `agenthub/streaming.py`, and `agenthub/backend.py` now share the same backend adapter path instead of duplicating backend logic.
- Initial `omnira` mode assumes an OpenAI-compatible endpoint and uses `config.yaml` values for `base_url`, `model`, and `api_key_env`.
- If OMNIRA later requires a custom API shape, the custom translation layer should be added in `agenthub/backend_client.py` without changing the desktop, CLI, or orchestration surfaces.
- Product intent: Jarvis/Desktop is the assistant shell; OMNIRA is the model core behind that shell.
- Repository boundary: Jarvis and OMNIRA are allowed to live in separate folders and separate repos. Jarvis only needs a reachable OMNIRA endpoint, not a co-located codebase.


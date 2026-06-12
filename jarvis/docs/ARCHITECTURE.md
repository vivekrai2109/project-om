# Architecture

## Overview
Jarvis is the owner-facing AI operator and control plane. Agent Hub is the internal multi-agent runtime that routes tasks to specialist agents while preserving project context, run history, approvals, policy boundaries, and memory.

## Core Components
- Orchestrator: plans work, selects agents, builds context, and enforces approvals
- Agents: specialist profiles with stable input and output contracts
- Router: keyword-based selection (initial, replace later with classifier)
- Memory: per-project summaries + run records
- Tool registry: central list of tools with risk and permission metadata
- CLI: entrypoint for local usage and automation
- Web UI: local control surface for runs, proposals, and review
- Queue: background execution for long-running tasks

## Operator and Runtime Split
- Jarvis owns user-facing interaction, approvals, policy, memory, and workflow supervision.
- Agent Hub owns specialist-agent execution, tool orchestration, and task handoffs.
- Model backends remain replaceable through one shared adapter layer.
- Self-hosted models should become the default path over time, with external models kept as fallback.

## Jarvis Lite Product Layers
- Capture: voice, optional session recording, and input events
- Understanding: transcript parsing, question detection, and task intent routing
- Orchestration: planner, router, agent execution, queueing
- Action: bounded tools with approval gates
- Coaching: summaries, scoring, and improvement loops
- Trust: auditability, policy boundaries, and personal/work separation

## Jarvis Versus OMNIRA
- Jarvis is the user-facing shell and control plane: desktop UI, CLI, local web UI, voice capture, approvals, sessions, persistence, runtime actions, and traces.
- OMNIRA is the backend intelligence layer: model routing, memory retrieval, safety evaluation, streaming chat, agent profiles, provider abstraction, and future RAG or model expansion.
- Jarvis connects to OMNIRA through an adapter and keeps the separation explicit.

## Desktop UI Contract
- The primary desktop experience should be `Tauri + React + WebGL/WebGPU`.
- The default mode is Presence Mode: central orb, small status chips, minimal transcript, and voice controls.
- Operations and diagnostics are hidden by default.
- Runtime details open only when requested, when approval is required, when an error occurs, or when debug mode is enabled.

## Desktop State Machine
- idle
- listening
- transcribing
- thinking
- speaking
- executing
- approval_required
- muted
- disconnected
- error

The desktop bridge is the owning abstraction for this state model. Frontend scenes derive from that bridge state instead of independently inventing UI state.

## Data Flow
1. User submits a task through CLI, web UI, or later a voice pipeline
2. Router selects an agent or workflow step (or the user specifies one)
3. Orchestrator composes system prompt, memory, and repo context
4. Model response or workflow result is returned
5. Run record, memory summary, and trace are persisted under `data/`

## Task Graph + Handoffs
For multi-step tasks, a planner generates a JSON plan and the orchestrator
executes each step with the appropriate specialist agent.

## Background Queue
Long tasks can be enqueued and processed by a local worker using file-based
queue storage under `data/queue/`.

## Local Web UI
The web UI provides a basic interface to run tasks and view recent runs. It is
served locally via FastAPI.

## Platform Reuse Status
The current reusable and refactor-needed modules are classified in `docs/PLATFORM_INVENTORY.md`.

## Design Docs
- `docs/README.md`
- `docs/ROADMAP.md`
- `docs/ARCHITECTURE_LAYERS.md`
- `docs/TECHNICAL_SPEC.md`
- `docs/MODEL_PLATFORM_STRATEGY.md`
- `docs/VOICE_CENTRIC_OPERATING_MODEL.md`
- `docs/PLATFORM_INVENTORY.md`
- `docs/NAMING_CONVENTIONS.md`

## Local-First Guarantees
- Project files are read-only for context
- Outputs are written to `data/` by default
- No background tasks without explicit invocation

## Learning Capture
- Jarvis writes structured interaction records under `data/interactions/`.
- These records are for review, analytics, and future OMNIRA training-data preparation.
- Jarvis does not fine-tune or retrain models automatically.

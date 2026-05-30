# Architecture

## Overview
Agent Hub is the platform core for Jarvis Lite: a local-first, supervised AI assistant that routes tasks to specialist agents while preserving project context, run history, approvals, and memory.

## Core Components
- Orchestrator: selects agent, builds context, calls model
- Agents: YAML profiles with system prompts and optional model overrides
- Router: keyword-based selection (initial, replace later with classifier)
- Memory: per-project summaries + run records
- Tool registry: central list of tools with default permissions
- CLI: entrypoint for local usage and automation
- Web UI: local control surface for runs, proposals, and review
- Queue: background execution for long-running tasks

## Jarvis Lite Product Layers
- Capture: voice, optional session recording, and input events
- Understanding: transcript parsing, question detection, and task intent routing
- Orchestration: planner, router, agent execution, queueing
- Action: bounded tools with approval gates
- Coaching: summaries, scoring, and improvement loops
- Trust: auditability, policy boundaries, and personal/work separation

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
- `docs/SYSTEM_DESIGN.md`
- `docs/ARCHITECTURE_LAYERS.md`
- `docs/APP_DESIGN.md`
- `docs/INFRA_DESIGN.md`
- `docs/NAMING_CONVENTIONS.md`
- `docs/FUNCTIONAL_SPEC.md`
- `docs/TECHNICAL_SPEC.md`

## Local-First Guarantees
- Project files are read-only for context
- Outputs are written to `data/` by default
- No background tasks without explicit invocation

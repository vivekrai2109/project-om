# Model Platform Strategy

## Scope

This document defines how Jarvis should reduce dependency on external AI vendors over time by making our own model stack the default execution path wherever practical.

## Goal

Jarvis should be a local-first personal AI operator whose orchestration, memory, policy, and approvals are owned by us, and whose inference increasingly runs on our own models.

The system should not depend on any single external AI provider for its core identity or operating model.

## Split

### Jarvis
- owner-facing operator and control plane
- voice, desktop, approvals, memory, workflows, audit, and policy boundaries

### Agent Hub
- internal multi-agent runtime
- planner, router, specialist agents, task contracts, tool execution, and workflow state

### Model Platform
- local or self-hosted inference stack
- fine-tuning and evaluation pipeline
- model registry, routing policy, and usage observability

### External Providers
- fallback capacity only
- temporary capability augmentation
- evaluation benchmark path

## Frontend
- Tauri 2 plus React and WebGL/WebGPU for the primary desktop shell
- voice-first interaction with typed fallback
- approval prompts, state chips, summaries, and session views
- Qt/QML only as a bridge path while the cinematic shell matures

## Backend
- Python 3.11+
- FastAPI for local control APIs and web surface
- Typer for CLI
- Pydantic for runtime contracts and config
- SQLite for structured local state
- JSONL for traces and append-only event logs
- workflow engine, approval engine, and policy engine inside the control plane

## Jarvis
- supervises work and delegates to specialist agents
- owns approvals, memory, policy, and audit
- must keep vendor-specific model logic behind one backend abstraction
- remains the local authority even when cloud workers or hosted models are used

## First Mission
- the first execution mission is Jarvis improving Jarvis inside this repo
- that includes self-coding, self-testing, self-bug-fixing, self-review, and supervised self-updates
- broader lifestyle automation should not outrank the self-development core until this loop is stable

## Models
- vLLM for OpenAI-compatible serving
- PyTorch plus Hugging Face ecosystem for training and packaging
- PEFT, LoRA, or QLoRA for efficient tuning
- MLflow or equivalent for experiment tracking and lineage
- self-hosted models should become default for routine workloads over time

## Memory
- short-term runtime state for the current task and session
- durable local memory for owner preferences, repo knowledge, and historical outcomes
- optional local vector retrieval for semantic recall across larger corpora
- retrieval policy chosen by Jarvis based on task type, cost, latency, and confidence
- internet learning should be domain-scoped, owner-visible, compute-aware, and safe-only by policy
- initial high-value external domains are finance, legal, cloud, networking, coding languages, systems design, and defensive security
- unsafe or unethical knowledge-ingestion categories should remain excluded even when internet learning is enabled

## Profile Learning
- Jarvis should build owner and user profiles primarily from explicit preferences, observed workflow patterns, and approved local traces
- profile learning should remain separately controllable from generic observation capture
- profile learning should enrich personalization and planning, not silently widen autonomy

## Owner
- owner or admin has unrestricted approved access to code, models, memory, and policies
- all non-owner autonomy remains bounded by policy and approval gates
- self-modification of core control logic remains owner-governed

## Rules

1. Local authority first
- approvals, identity, policy, secrets boundary, and memory remain local-first

2. Single backend abstraction
- every model call must pass through one backend-routing layer
- desktop, CLI, orchestrator, and agents should not know vendor-specific details

3. Own-model-first migration
- prefer self-hosted models when they meet the quality bar for a task class
- use external models only when quality, latency, or reliability requires fallback

4. Supervised self-improvement
- Jarvis can propose changes to prompts, workflows, and code
- core updates require owner approval and validation

5. Owner override
- owner or admin can stop, pause, approve, reject, or kill active autonomous loops
- kill-switch control must exist outside any single agent workflow

6. Measurable quality
- model decisions must be observable with usage, latency, task outcome, and fallback metrics

## Runtime
- YAML agent definitions with Pydantic envelopes
- centralized tool registry with risk metadata
- local queue backed by SQLite first, with Redis only if scale requires it later

## Speech
- current speech abstraction stays in Python
- Whisper-class transcription or equivalent local speech stack when feasible
- lip-reading or silent visual speech interpretation is advanced R&D, not first-wave MVP
- camera or presence inputs should stay optional, visible, and owner-controlled

## Stages

### Stage 1 - External bootstrap
- keep external APIs available
- add full backend abstraction and usage logging
- start collecting approved traces and eval sets

### Stage 2 - Hybrid routing
- use own models for routing, summarization, tagging, and memory extraction
- fallback to stronger external models for hard reasoning or poor-confidence cases

### Stage 3 - Own-model default
- use own models by default for routine planning, repo understanding, and common operator tasks
- keep external models as exception paths only

### Stage 4 - Supervised self-improvement
- use approved traces for targeted fine-tuning and eval loops
- allow Jarvis to propose model, prompt, and workflow upgrades under approval

## Metrics

Each model-backed run should capture:
- model family and endpoint
- task class
- prompt tokens or equivalent usage units
- completion tokens or equivalent usage units
- latency
- hardware or cost estimate
- fallback reason if another provider was used
- success or failure signal
- optional quality rating or eval score

## Gates

The following must require explicit owner or admin approval:
- financial actions or trading execution
- purchases or ordering actions
- account access changes
- destructive file or infrastructure actions
- outbound communication on behalf of the user
- self-modification of security, policy, or approval logic
- deployment of new model-routing rules that widen autonomy

## Controls
- provide terminal and voice-accessible `start`, `stop`, `pause`, and `kill` controls
- keep kill state global, immediate, and auditable
- allow Jarvis to continue safe passive functions after a kill event only when explicitly restarted by the owner

## Build Order

1. define the self-development core and owner-control model
2. unify the backend abstraction layer
3. define stable supervisor and specialist-agent contracts
4. add model usage observability
5. add layered memory and retrieval policy
6. default low-risk tasks to self-hosted models
7. build eval loops and fallback policy
8. add supervised self-improvement flows

## Success

The strategy is working when:
- Jarvis can run common operator tasks on our own models by default
- external provider use is visible, intentional, and steadily decreasing
- owner approvals remain enforceable regardless of model backend
- model upgrades can happen without rewriting Jarvis product surfaces
- training and eval loops improve quality without weakening safety boundaries

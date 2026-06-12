# Roadmap

This roadmap reframes Agent Hub as the core platform for Jarvis Lite: a local-first, supervised AI operator for project work, personal workflows, voice-driven interaction, and owner-governed autonomy.

## Phase 0 - Platform Base (Done or Mostly Done)
- [x] Centralized agent profiles
- [x] Local CLI entrypoints
- [x] Local run logs and project memory storage
- [x] Planner-driven multi-step workflows
- [x] Background queue primitives
- [x] Local web UI foundation
- [x] Basic tracing and run persistence

## Phase 1 - Product Framing (Now)
- [x] Define Jarvis Lite product direction
- [x] Add MVP document and scope boundaries
- [x] Define Jarvis as the owner-facing operator over a multi-agent runtime
- [x] Align README, roadmap, tasks, and architecture docs for the current Jarvis shell direction
- [ ] Identify which existing Agent Hub modules are reusable without redesign
- [ ] Separate framework features from product features in docs
- [ ] Publish the own-model-first platform strategy and backend migration plan

## Phase 1.5 - Self-Development Core
- [ ] Make self-coding, self-testing, self-bug-fixing, and self-improvement the first execution mission
- [ ] Let Jarvis route implementation work to specialist sub-agents under owner-governed approval
- [ ] Add proposal, test, eval, patch, and rollback loops before broad lifestyle automation
- [ ] Keep owner or admin override on any core-policy, model-routing, or self-update change

## Phase 2 - Safe Personal Operator Core
- [ ] Add user profiles for personal and work contexts
- [ ] Add explicit owner and admin role with unrestricted authority over approved code and model surfaces
- [ ] Define permission model for tools, folders, commands, and apps
- [ ] Add approval workflows for risky actions
- [ ] Add better audit history for executed actions
- [ ] Add configurable allowlists and deny lists
- [ ] Add global stop, pause, and kill-switch controls for terminal, desktop, and voice entry points

## Phase 2.5 - Agentic Runtime Contracts
- [ ] Formalize supervisor-to-sub-agent handoff contracts
- [ ] Separate operator planning from specialist agent execution
- [ ] Add workflow state, task ownership, and result contracts across agents
- [ ] Classify agents by local-only, hybrid, or cloud-allowed execution
- [ ] Add guarded delegation rules for finance, work, and destructive domains

## Phase 3 - Voice Command Layer
- [x] Add microphone capture pipeline
- [x] Add speech-to-text integration
- [ ] Add camera and presence-input foundations for visible owner-aware interaction
- [ ] Route voice transcripts through the existing planner/router flow
- [x] Add text-to-speech responses for optional voice feedback
- [x] Add push-to-talk or visible listen mode
- [ ] Make the desktop shell voice-primary and treat typing as fallback only
- [ ] Support spoken operator tasks for search, download, desktop actions, and error recovery

## Phase 3.5 - Cinematic Desktop Shell
- [ ] Separate desktop presentation concerns from assistant core logic
- [ ] Define a stable desktop-facing service boundary for voice, sessions, and streaming
- [ ] Promote `Tauri + React + WebGL/WebGPU` to the production cinematic shell after the OMNIRA backend is live instead of mock
- [ ] Keep Tkinter and Qt paths only as temporary bridge shells during migration
- [ ] Design state-driven scenes for idle, listening, thinking, speaking, and approval states
- [ ] Add cinematic audio visualization and animated assistant-core surfaces
- [ ] Add depth, shader, particle, and parallax effects for a stronger assistant presence
- [ ] Keep OMNIRA integration behind the existing backend adapter so UI migration does not change model routing

## Phase 3.6 - Operator Shell Hardening
- [x] Add a dedicated popup Jarvis shell launcher in the workspace root
- [x] Add shell-native `/voice`, `/omnira`, and `/autonomy` operator status commands
- [x] Surface when the OMNIRA backend is still running on the mock provider
- [ ] Replace the mock OMNIRA process on port `8001` with the live Ollama-backed API
- [ ] Add token-by-token conversational streaming to the terminal shell

## Phase 4 - Interview Coach MVP
- [ ] Add consent-based session recording
- [ ] Add transcript segmentation for question and answer turns
- [ ] Detect question categories and answer structure
- [ ] Produce post-session coaching summaries
- [ ] Track recurring improvement areas over time

## Phase 5 - Personal Operator Workflows
- [ ] Add browser and desktop workflows for user-approved actions
- [ ] Add bounded personal-life workflows such as ordering, scheduling, and reminders
- [ ] Add note search, calendar/task actions, and project helper commands
- [ ] Add reusable workflows for coding, research, and documentation tasks
- [ ] Add session summaries with next-step recommendations

## Phase 5.5 - Supervised Self-Improvement
- [ ] Capture structured traces suitable for model improvement and eval loops
- [ ] Let Jarvis propose workflow, prompt, and code improvements under approval
- [ ] Add regression checks before any core self-update is applied
- [ ] Allow low-risk memory and preference adaptation without core-policy mutation

## Phase 6 - Hardening and Reliability
- [ ] Decouple CLI startup from optional web dependencies
- [ ] Add focused integration tests for CLI, queue, and web flows
- [ ] Add cost, latency, and failure reporting
- [ ] Improve retry policies and failure recovery
- [ ] Add packaging guidance for repeatable local installs

## Phase 7 - Own Model Platform
- [ ] Route all model calls through one backend abstraction with usage accounting
- [ ] Make local or self-hosted models the default for routing, memory, and summarization
- [ ] Add memory and retrieval architecture that lets Jarvis choose between local memory, vector search, or direct tools by task type
- [ ] Add eval-driven fallback from own models to stronger external models when needed
- [ ] Stand up fine-tuning, model registry, and experiment tracking for Jarvis workloads
- [ ] Track tokens, latency, hardware cost, and task success per model family

## Phase 8 - Hybrid Scale and Cloud Extension
- [ ] Add remote access architecture for always-on usage
- [ ] Add secure secret storage and sync strategy
- [ ] Add cloud workers for burst execution while keeping local authority
- [ ] Add infra self-observability so Jarvis can inspect its own runtime health
- [ ] Add cloud deployment options only after laptop MVP and owner controls are stable

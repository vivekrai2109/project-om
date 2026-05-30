# Roadmap

This roadmap reframes Agent Hub as the core platform for Jarvis Lite: a local-first, supervised AI assistant for project work, voice-driven workflows, and interview coaching.

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
- [ ] Align README, roadmap, tasks, and architecture docs fully
- [ ] Identify which existing Agent Hub modules are reusable without redesign
- [ ] Separate framework features from product features in docs

## Phase 2 - Safe Personal Operator
- [ ] Add user profiles for personal and work contexts
- [ ] Define permission model for tools, folders, commands, and apps
- [ ] Add approval workflows for risky actions
- [ ] Add better audit history for executed actions
- [ ] Add configurable allowlists and deny lists

## Phase 3 - Voice Command Layer
- [ ] Add microphone capture pipeline
- [ ] Add speech-to-text integration
- [ ] Route voice transcripts through the existing planner/router flow
- [ ] Add text-to-speech responses for optional voice feedback
- [ ] Add push-to-talk or visible listen mode
- [ ] Make the desktop shell voice-primary and treat typing as fallback only
- [ ] Support spoken operator tasks for search, download, desktop actions, and error recovery

## Phase 3.5 - Cinematic Desktop Shell
- [ ] Separate desktop presentation concerns from assistant core logic
- [ ] Define a stable desktop-facing service boundary for voice, sessions, and streaming
- [ ] Replace the Tkinter prototype with a `PySide6 + QML` desktop shell
- [ ] Design state-driven scenes for idle, listening, thinking, speaking, and approval states
- [ ] Add cinematic audio visualization and animated assistant-core surfaces
- [ ] Keep OMNIRA integration behind the existing backend adapter so UI migration does not change model routing

## Phase 4 - Interview Coach MVP
- [ ] Add consent-based session recording
- [ ] Add transcript segmentation for question and answer turns
- [ ] Detect question categories and answer structure
- [ ] Produce post-session coaching summaries
- [ ] Track recurring improvement areas over time

## Phase 5 - Personal Operator Workflows
- [ ] Add browser and desktop workflows for user-approved actions
- [ ] Add note search, calendar/task actions, and project helper commands
- [ ] Add reusable workflows for coding, research, and documentation tasks
- [ ] Add session summaries with next-step recommendations

## Phase 6 - Hardening and Reliability
- [ ] Decouple CLI startup from optional web dependencies
- [ ] Add focused integration tests for CLI, queue, and web flows
- [ ] Add cost, latency, and failure reporting
- [ ] Improve retry policies and failure recovery
- [ ] Add packaging guidance for repeatable local installs

## Phase 7 - Optional Cloud and Local Model Expansion
- [ ] Add remote access architecture for always-on usage
- [ ] Add secure secret storage and sync strategy
- [ ] Add local model runtime path for privacy-first deployments
- [ ] Add cloud deployment options only after laptop MVP is stable

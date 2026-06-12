# Tasks

This file tracks the next concrete execution tasks for Jarvis Lite on top of the existing Agent Hub platform.

## Stage 1 - Product Framing
- [x] Define the legitimate product direction for Jarvis Lite
- [x] Add an MVP document with scope, non-goals, and milestones
- [x] Rewrite the roadmap around a supervised personal assistant
- [x] Define Jarvis as the owner-facing operator over the internal agentic runtime
- [ ] Update architecture and functional spec docs to match the new direction
- [ ] Publish the own-model-first strategy and model migration stages
- [ ] Decide the first user journey to optimize: interview coach or personal operator shell

## Stage 2 - Platform Stabilization
- [x] Decouple CLI startup from optional web dependencies
- [ ] Verify install and startup on a clean local environment
- [x] Audit the current command set against README and docs
- [ ] Add focused validation for `run`, `plan`, `run-plan`, `worker`, and `web`
- [x] Classify current modules as reusable, needs-refactor, or product-specific
- [x] Add a root-folder launcher that opens Jarvis in its own shell window

## Stage 2.2 - Self-Dev Core
- [ ] Make repo self-development the first mission before broader personal-operator automation
- [ ] Let Jarvis create coding, testing, bug-fixing, and review tasks for specialist sub-agents
- [ ] Require test and eval evidence before self-generated patches can be promoted
- [ ] Add rollback and recovery paths for failed self-updates

## Stage 2.5 - Agent Contracts
- [ ] Define the supervisor contract for Jarvis to create, route, and review sub-agent tasks
- [ ] Define a standard input/output envelope for specialist agents
- [ ] Define approval checkpoints between planning, tool execution, and external side effects
- [ ] Tag each agent as local-only, hybrid, or cloud-allowed

## Stage 3 - Safety and Permissions
- [x] Define personal and work profile boundaries
- [x] Add per-tool risk levels and approval rules
- [x] Add allowlists for paths, commands, and apps
- [x] Persist action audit history separately from model run logs
- [x] Define recording consent rules for interview practice sessions
- [ ] Add explicit finance and purchase approval rails
- [ ] Add owner/admin-only controls for core policy and self-update flows
- [ ] Add hard stop, soft stop, and emergency kill-switch flows for terminal, voice, and desktop sessions

## Stage 4 - Voice Command Shell
- [x] Add microphone capture service
- [x] Add speech-to-text provider abstraction
- [x] Convert transcripts into routed tasks
- [x] Add visible listen state and push-to-talk control
- [x] Add optional text-to-speech responses
- [ ] Add owner-presence inputs for camera-aware or visual-state workflows
- [ ] Add a real shell microphone conversation loop instead of status-only voice control

## Stage 5 - Interview Coach MVP
- [x] Add session creation and recording workflow
- [x] Persist transcripts and question-answer segments
- [x] Add question classification and answer scoring
- [x] Generate post-session coaching summaries
- [x] Store recurring weaknesses and suggested drills

## Stage 6 - Personal Operator Workflows
- [ ] Add safe file and terminal workflows through approval gates
- [ ] Add browser-based helper actions for user-approved tasks
- [ ] Add project-aware workflows for code, docs, and repo scans
- [ ] Add reusable workflow templates for common commands
- [x] Add operator-facing shell commands for OMNIRA status, autonomy status, and live learning visibility

## Stage 6.5 - Own Model Adoption
- [ ] Send all inference through a single backend-routing layer
- [ ] Add model usage telemetry for tokens, latency, and fallback reasons
- [ ] Default routing, summarization, and memory tasks to self-hosted models
- [ ] Add layered memory with short-term state, durable memory, and vector retrieval for project and owner context
- [ ] Add eval comparisons between own models and external providers
- [ ] Keep external providers as explicit fallback only
- [ ] Restart OMNIRA on port `8001` so Jarvis stops talking to the mock provider and starts using the installed Ollama models

## Stage 7 - Review and Adaptation
- [ ] Add progress views for interview improvement
- [ ] Add user preference memory for response style and coaching focus
- [ ] Add session comparisons and trend summaries
- [ ] Add quality and reliability metrics for assistant actions

## Stage 8 - Supervised Self-Improvement
- [ ] Capture training candidates from approved real-world runs
- [ ] Let Jarvis propose prompt, workflow, and code improvements
- [ ] Require approval plus regression checks before core updates apply
- [ ] Add rollback paths for failed self-updates

# Tasks

This file tracks the next concrete execution tasks for Jarvis Lite on top of the existing Agent Hub platform.

## Stage 1 - Product Framing
- [x] Define the legitimate product direction for Jarvis Lite
- [x] Add an MVP document with scope, non-goals, and milestones
- [x] Rewrite the roadmap around a supervised personal assistant
- [ ] Update architecture and functional spec docs to match the new direction
- [ ] Decide the first user journey to optimize: interview coach or personal operator shell

## Stage 2 - Platform Stabilization
- [x] Decouple CLI startup from optional web dependencies
- [ ] Verify install and startup on a clean local environment
- [x] Audit the current command set against README and docs
- [ ] Add focused validation for `run`, `plan`, `run-plan`, `worker`, and `web`
- [x] Classify current modules as reusable, needs-refactor, or product-specific

## Stage 3 - Safety and Permissions
- [x] Define personal and work profile boundaries
- [x] Add per-tool risk levels and approval rules
- [x] Add allowlists for paths, commands, and apps
- [x] Persist action audit history separately from model run logs
- [x] Define recording consent rules for interview practice sessions

## Stage 4 - Voice Command Shell
- [x] Add microphone capture service
- [x] Add speech-to-text provider abstraction
- [x] Convert transcripts into routed tasks
- [x] Add visible listen state and push-to-talk control
- [ ] Add optional text-to-speech responses

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

## Stage 7 - Review and Adaptation
- [ ] Add progress views for interview improvement
- [ ] Add user preference memory for response style and coaching focus
- [ ] Add session comparisons and trend summaries
- [ ] Add quality and reliability metrics for assistant actions

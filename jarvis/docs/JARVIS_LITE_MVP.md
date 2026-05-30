# Jarvis Lite MVP

## Product Summary

Jarvis Lite is a supervised, local-first AI assistant built on top of Agent Hub. The first release should behave like a personal operator with voice input, explicit approvals for risky actions, project-aware context, and a focused interview coaching workflow.

The MVP should be practical on a laptop and should not require cloud hosting beyond optional AI APIs.

## Primary Use Cases

### 1. Voice-first personal operator
- listen for a push-to-talk or wake action
- transcribe spoken requests
- route requests to the correct agent or workflow
- execute approved actions on the local machine
- keep voice as the primary UI contract while visuals show progress, approvals, and outcomes

### 2. Project assistant
- inspect repositories
- summarize files and plans
- run bounded development workflows
- draft patches, docs, and task breakdowns

### 3. Interview coach
- record practice sessions with user consent
- transcribe questions and answers
- classify question types
- score answers for structure, clarity, depth, and conciseness
- generate coaching feedback and improvement plans

## Explicit Non-Goals
- covert assistance in live interviews
- hidden overlays or undisclosed answer feeds
- analysis of other people without their knowledge and consent
- unrestricted machine control without approvals

## MVP Capabilities

## A. Capture Layer
- microphone input
- optional webcam input for self-review
- optional screen capture for user-owned practice sessions
- session start and stop controls
- visible recording state

## B. Understanding Layer
- speech-to-text transcription
- question segmentation
- task intent detection
- repo-aware context assembly

## C. Orchestration Layer
- agent routing
- single-task execution
- multi-step planning
- background queue for long-running tasks

## D. Action Layer
- local file read and write tools
- terminal execution with approvals
- browser automation for user-approved tasks
- per-tool and per-profile access policies
- spoken operator workflows for repo search, downloads, desktop handling, and error investigation

## E. Coaching Layer
- answer scoring rubric
- STAR and structured-answer guidance
- filler word and pacing analysis
- post-session summaries
- personalized drills for weak areas

## F. Trust and Safety Layer
- explicit approval prompts for risky actions
- audit log of actions taken
- personal and work profile separation
- local-first data retention by default

## Suggested MVP Architecture

### Desktop app
- native desktop shell first, with cinematic presentation as a product goal
- recommended production UI stack: `PySide6 + QML`
- keep the current Tkinter shell only as a prototype bridge while the production shell is built
- push-to-talk control
- session timeline and approvals panel

### Backend core
- existing Agent Hub orchestrator
- workflow engine for multi-step tasks
- memory, tracing, and run persistence

### AI services
- cloud APIs first for LLM, STT, and optional TTS
- local model support later for privacy and cost control

### Storage
- local data directory for runs, memory, traces, and session artifacts
- optional encrypted secrets storage

## MVP Milestones

### Milestone 1: Product framing
- define product scope and safety rules
- align README, roadmap, and docs
- identify reusable Agent Hub components

### Milestone 2: Voice command shell
- add voice input pipeline
- support transcript-to-task routing
- add confirmations for risky actions

### Milestone 3: Interview coaching workflow
- capture practice sessions
- produce transcripts and question segmentation
- generate answer feedback and summaries

### Milestone 4: Personal operator workflows
- open apps and files
- search notes and repos
- run approved project tasks

### Milestone 5: Review and adaptation
- track recurring mistakes
- build personalized coaching memory
- add progress dashboards

## Hardware Recommendation
- laptop is sufficient for MVP
- 16 GB RAM minimum, 32 GB preferred
- decent microphone or headset recommended
- webcam optional for self-review
- no cloud hosting required for the first release

## Viability Test

The MVP is viable if it can do all of the following on a laptop:
- take a voice command and route it correctly
- execute a safe, approved local action
- run a project-aware task inside a repo
- record a practice interview session with consent
- generate a useful coaching summary after the session
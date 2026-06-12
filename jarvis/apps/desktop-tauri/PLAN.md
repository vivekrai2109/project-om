# Shell Plan

## Goal

Turn the current Tauri scaffold into the production cinematic Jarvis shell.

## Frontend

### Stack
- Tauri 2
- React 19
- TypeScript
- Vite
- Three.js
- React Three Fiber
- Motion or Framer Motion
- Web Audio analysis for microphone-reactive visuals

### Build
1. keep the current app shell and API wiring
2. add scene architecture for `boot`, `idle`, `listening`, `thinking`, `speaking`, `approval_required`, and `error`
3. add a central assistant-core renderer
4. add orbital chips, edge panels, and approval overlays
5. add audio-reactive motion
6. add streaming and transition choreography

### UI Rule
- default to presence mode, not dashboard mode
- keep text secondary to motion, state, and concise summaries
- keep operator diagnostics hidden unless needed

## Backend

### API
- keep local HTTP for initial integration
- add streaming-friendly endpoints or WebSocket bridge for state events
- expose stable contracts for:
  - session state
  - voice state
  - approval queue
  - streaming assistant output
  - active workflow state

### Runtime Needs
- predictable assistant state machine
- approval event feed
- microphone and listen-state updates
- backend health and model status

## Jarvis

### Ownership
- Jarvis owns orchestration
- Jarvis owns approvals and policy checks
- Jarvis owns memory and sessions
- Jarvis owns model routing and provider choice

### Contracts
- UI should consume state, not infer business logic
- sub-agent work should surface as workflow state and summaries, not raw internal prompts
- risky actions must surface explicit approval objects

## Models

### UI Expectations
- model choice should not change shell behavior directly
- shell reacts to runtime state such as thinking, streaming, confidence, approval wait, or error

### Near-Term
- show active model family and backend health only in operations or debug surfaces
- keep vendor details out of presence mode

## Phases

### Phase 1
- clean app structure
- add layout primitives
- add scene state store
- replace current static orb with scene-driven assistant core

### Phase 2
- add React Three Fiber scene
- add shader materials and particle layers
- add animated microphone response

### Phase 3
- add streaming response surface
- add approval overlays
- add session and insight panels

### Phase 4
- add operations and debug drawers
- add backend health, model info, and workflow trace views

### Phase 5
- polish motion, lighting, sound response, and fallback behavior
- retire Tkinter for daily use
- demote the Qt bridge once parity is proven

## Current Blockers
- Rust toolchain missing for native Tauri runs
- frontend currently lacks Three.js and motion dependencies
- backend contracts for richer cinematic state are still thin

## First Tasks
1. install Rust toolchain on the workstation
2. add Three.js, React Three Fiber, and motion dependencies
3. define the UI-facing Jarvis state contract
4. refactor the current app into scene, shell, and data modules
5. build the first presence-mode scene
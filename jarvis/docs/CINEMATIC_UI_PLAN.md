# Cinematic UI Plan

## Decision

Jarvis should use `Tauri + React + WebGL/WebGPU` as the production cinematic shell.

This is the best fit for an industry-grade cinematic assistant because it gives Jarvis:
- stronger shader and particle rendering
- better depth, parallax, and layered motion
- higher frontend iteration speed
- easier use of advanced web animation and 3D libraries
- a cleaner path to a living assistant presence instead of a utility dashboard

`PySide6 + QML` should remain only as a bridge path while the production shell matures.

## Frontend
- Tauri 2 desktop shell
- React 19 + TypeScript + Vite
- React Three Fiber over Three.js for the assistant core scene
- WebGL first, with WebGPU adoption when the renderer path is ready
- Motion library for transitions and choreography
- custom shader pipeline for glow, pulse, scan, particles, and ambient depth
- Web Audio driven visual response for live microphone activity

## Backend
- Python Jarvis core remains the control plane
- local HTTP or WebSocket bridge between shell and Jarvis runtime
- backend owns sessions, approvals, memory, orchestration, and model calls
- frontend remains a presentation and interaction layer, not a business-logic layer

## Jarvis
- owns conversation state, agent routing, approvals, voice controls, and system status
- exposes stable UI-facing contracts for stream updates, session sync, approval prompts, and voice state
- keeps OMNIRA and model routing behind the backend adapter

## Models
- model providers do not decide UI state
- UI reacts to runtime state, not vendor-specific responses
- voice and response timing can animate differently by task class or confidence, but the control source remains Jarvis

## Why Tkinter Stops Short

The current shell in `agenthub/desktop.py` can support:
- functional desktop controls
- simple HUD styling
- basic waveform and status animation

It cannot comfortably support:
- cinematic compositing
- strong transparency, blur, and glow pipelines
- shader-driven scenes
- audio-reactive 3D motion
- layered camera depth and parallax systems

## Why Tauri Wins

Compared with the Qt bridge, Tauri plus a modern web rendering stack gives Jarvis:
- better access to advanced animation libraries
- better access to 3D scene tooling
- easier shader iteration
- stronger hiring and contributor familiarity
- a clearer path to a premium cinematic product surface

## State

The cinematic shell should be built around explicit assistant states:
- `boot`
- `idle`
- `listening`
- `thinking`
- `speaking`
- `approval_required`
- `warning`
- `error`

Each state should change:
- color treatment
- motion intensity
- waveform behavior
- central-core animation
- side-panel visibility and emphasis

## Visual System

The new UI should move away from dashboard boxes and toward:
- one central assistant-core visual anchor
- radial or orbital information layers
- cinematic depth and parallax
- low-text high-signal status chips
- edge-mounted secondary panels
- motion-led feedback instead of static labels

## Animation Stack

Recommended rendering and motion stack:
- Tauri 2
- React 19
- TypeScript
- Vite
- Three.js
- React Three Fiber
- shader materials for pulse, glow, scan, and particle fields
- Motion or Framer Motion for 2D transitions
- Web Audio analysis for waveform and orb response

## Migration

1. Stabilize a desktop-facing interface in Python for message send, response stream, backend status, session list, microphone state, listen mode, approvals, and TTS control.
2. Keep Tkinter and Qt paths available only as temporary bridge shells.
3. Build the Tauri shell with boot, idle, and conversation streaming.
4. Add audio-reactive visuals and approval overlays.
5. Add session browsing, insights, and diagnostics surfaces.
6. Retire Tkinter after parity for daily use.
7. Retire or demote the Qt bridge once the Tauri shell is stable.

Implementation detail for the Tauri app lives in `apps/desktop-tauri/PLAN.md`.

## Scope Rule

"4D" should be treated as a cinematic product goal, not a literal rendering requirement. The implementation target is a layered 2D and 3D assistant presence with depth, motion, lighting, parallax, and audio-reactive behavior.
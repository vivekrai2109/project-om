# Cinematic UI Plan

## Decision

Jarvis should move from the current Tkinter prototype to a `PySide6 + QML` desktop shell.

This is the best near-term choice because:
- Jarvis is already a Python-first runtime
- the assistant core, voice stack, memory, and OMNIRA adapter already live in Python
- QML gives a much stronger animation and composition system than Tkinter without forcing a full backend rewrite

`Tauri + React/WebGL` remains the stronger long-term option only if the visual target becomes much more cinematic than a native Qt scene can comfortably provide.

## Why Tkinter Stops Short

The current shell in `agenthub/desktop.py` can support:
- functional desktop controls
- simple HUD styling
- basic waveform and status animation

It cannot comfortably support:
- cinematic compositing
- layered transparency and blur
- richer transition choreography
- high-fidelity radial HUD systems
- shader-style effects and fluid scene motion

## Recommended Architecture

Jarvis should be split into two layers:

### 1. Jarvis Core
- Python runtime
- voice and microphone control
- backend routing and OMNIRA integration
- session and memory persistence
- orchestration, approvals, and task execution

### 2. Jarvis Shell
- `PySide6 + QML`
- scene rendering
- animated conversation surfaces
- voice-state visualization
- approval overlays
- desktop interaction controls

The shell should call the Python core through a thin application boundary, not embed business logic in UI files.

## Scene System

The cinematic shell should be built around explicit assistant states:
- `boot`
- `idle`
- `listening`
- `thinking`
- `speaking`
- `approval_required`
- `warning`

Each state should change:
- color treatment
- motion intensity
- waveform behavior
- central-core animation
- side-panel visibility and emphasis

## Core Visual Language

The new UI should move away from dashboard boxes and toward:
- one central assistant-core visual anchor
- radial or orbital information layers
- edge-mounted secondary panels
- low-text high-signal status chips
- motion-led feedback instead of static labels

## Migration Steps

1. Stabilize a desktop-facing interface in Python for message send, response stream, backend status, session list, microphone state, listen mode, and TTS control.
2. Keep the current Tkinter shell operational during the migration.
3. Build a minimal `PySide6 + QML` shell that supports boot, idle, and conversation streaming.
4. Add voice-state visuals and approval overlays.
5. Port session browsing and system diagnostics.
6. Remove the Tkinter shell only after parity for daily use.

## When To Choose Tauri Instead

Switch to `Tauri + React/WebGL` if Jarvis later needs:
- heavy custom motion design
- 3D or shader-driven scenes
- browser-grade rendering libraries
- rapid visual experimentation by frontend-focused contributors

If that happens, keep the same Jarvis Python core and expose it through a local API or local WebSocket bridge.
# Jarvis Shell

This app is the production desktop-shell path for Jarvis.

## Frontend
- Tauri 2 shell
- React 19
- TypeScript
- Vite
- current scaffold is 2D UI first
- target path is cinematic rendering with WebGL or WebGPU

## Backend
- talks to the Jarvis Python runtime over local HTTP today
- expected endpoints include `/jarvis/state` and `/chat`
- later path can add local WebSocket streaming for richer state and animation timing

## Jarvis
- Jarvis remains the control plane
- approvals, memory, sessions, voice state, and orchestration stay in Python
- this app should stay a presentation and interaction layer

## Models
- model routing stays behind Jarvis
- OMNIRA, self-hosted models, and fallback providers should be invisible to the shell except through runtime state

## Current
- React and Vite scaffold exists
- Tauri config exists
- basic backend API wiring exists
- cinematic rendering stack is not integrated yet

## Gap
- Rust toolchain is not installed on this machine yet
- `npm run dev` can be used for frontend work
- `npm run tauri:dev` remains blocked until `cargo` and `rustc` are installed

## Run

```powershell
npm install
npm run dev
```

After Rust is installed:

```powershell
npm install
npm run tauri:dev
```

## API

Default backend URL:

```text
http://127.0.0.1:8010
```

Override:

```powershell
$env:VITE_JARVIS_API_URL="http://127.0.0.1:8010"
```

## Plan

See `PLAN.md` in this folder for the implementation phases.
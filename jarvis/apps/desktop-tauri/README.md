# Jarvis Tauri Shell

This folder contains the new `Tauri + React` desktop shell for Jarvis.

## Role

- richer visual shell for Jarvis as a holistic personal assistant and AI commander
- thin UI over the existing Python Jarvis core and OMNIRA backend
- voice-first design with a compact fallback terminal instead of a text-heavy desktop surface

## Current State

- React/Vite frontend scaffolded
- Tauri configuration scaffolded
- wired to the current Jarvis backend API (`/jarvis/state` and `/chat`)

## Toolchain Gap

This machine currently has `node` and `npm`, but does **not** have the Rust toolchain (`cargo`, `rustc`).

That means you can develop the frontend layer now, but native Tauri build/dev commands will not run until Rust is installed.

## Commands

```powershell
npm install
npm run dev
```

After Rust is installed:

```powershell
npm install
npm run tauri:dev
```

## Backend Expectation

The shell expects the Jarvis backend API to be available, defaulting to:

```text
http://127.0.0.1:8010
```

Override with:

```powershell
$env:VITE_JARVIS_API_URL="http://127.0.0.1:8010"
```
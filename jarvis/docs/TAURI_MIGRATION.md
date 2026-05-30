# Tauri Migration

## Why Tauri

`Tauri + React` gives Jarvis a higher visual ceiling than the current Qt/QML shell when the goal is a cinematic, sci-fi, living assistant surface.

It improves:

- motion design flexibility
- theme layering and atmosphere
- glass/shader-like visual direction
- component iteration speed
- frontend contributor velocity

## How It Fits Jarvis

Jarvis remains split into:

1. Python core
   - voice, memory, approvals, runtime actions, OMNIRA integration

2. Desktop shell
   - Tauri wrapper
   - React/Vite frontend
   - talks to the Python Jarvis backend over local HTTP for now

## Current Repo Addition

The first Tauri shell scaffold now lives in:

- `apps/desktop-tauri/`

It is intentionally thin and does not replace the current Qt/QML path yet.

## Toolchain Constraint

This machine does not currently have:

- `cargo`
- `rustc`

So the Tauri shell is scaffolded, but native Tauri build/run commands are blocked until the Rust toolchain is installed.

## Next Steps

1. Install Rust toolchain.
2. Run `npm install` inside `apps/desktop-tauri`.
3. Run `npm run tauri:dev`.
4. Expand the shell with voice-state visuals, commander cards, approvals, and assistant presence.
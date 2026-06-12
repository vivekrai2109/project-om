# current status

This file tracks the current implemented Jarvis shell, OMNIRA backend status, learning surfaces, and autonomy level.

## shell

- clickable root launcher exists as `Project-OM/JARVIS Shell.cmd`
- popup shell command exists as `agenthub shell-window`
- shell supports `/status`, `/today`, `/voice`, `/omnira`, `/autonomy`, `/approvals`, `/approve`, and `/reject`
- quick conversational prompts such as `who are you` and `do you understand me` are handled locally before broader backend routing

## omnira

- Jarvis currently points at `http://127.0.0.1:8001`
- the active backend reports `provider: mock`
- local Ollama is installed on this machine
- local models `qwen2.5:3b` and `qwen2.5:7b` are installed
- the missing step is replacing the current mock process on port `8001` with the live Ollama-backed OMNIRA API process

## learning

- local interaction records are stored under `jarvis/data/interactions/`
- local learning records are stored under `jarvis/data/learning/`
- promoted training candidates are stored under `jarvis/data/training_candidates/`
- OMNIRA training configs currently live under `omnira-ai/training/configs/`
- internet learning remains owner-controlled and is currently off by default
- screen sharing and camera learning are not active in this terminal shell today

## autonomy

- current mode is supervised autonomy
- Jarvis can chat, route tasks, record learning, prepare changes, run safer actions, and request approval on risky work
- full autonomy is still blocked by approval gates, inactive camera/screen perception, owner-controlled internet learning, and the mock backend still running on the live Jarvis endpoint

## next high-value steps

1. restart OMNIRA on port `8001` with the live Ollama-backed API
2. add token-by-token streaming in the terminal shell
3. add a real microphone-driven shell conversation loop
4. add stronger eval and regression gates before broad autonomy
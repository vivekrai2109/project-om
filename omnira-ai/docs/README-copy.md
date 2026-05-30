# OMNIRA AI

OMNIRA AI is a modular personal intelligence platform designed to grow from a local-first MVP into a private Jarvis-style system with chat, memory, RAG, agents, model routing, tool execution, training workflows, and evaluations.

## Platform Names

- Brand: OMNIRA AI
- Tagline: Your Personal Intelligence OS
- Backend: OMNIRA Core
- UI: OMNIRA Studio
- Orchestrator: OMNIRA Prime
- Memory Layer: OMNIRA Memory
- Agent System: OMNIRA Agents
- Training Workspace: OMNIRA Lab
- Evaluation System: OMNIRA Bench

## Developer Commands

### Start the backend

```powershell
Set-Location apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

### Start the frontend

```powershell
Set-Location apps/api
.\.venv\Scripts\Activate.ps1
Set-Location apps/web
npm.cmd install
npm run dev
```

This uses the same shell session after activating the Python virtual environment, but Node packages still install into `apps/web/node_modules`, not into the Python venv.

### Run tests

```powershell
Set-Location apps/api
.\.venv\Scripts\Activate.ps1
pytest
```

### Use Ollama later

```powershell
ollama serve
ollama create omnira-platform -f inference/ollama/Modelfile.omnira-platform
```

### Run OMNIRA with Ollama locally

1. Install Ollama from https://ollama.com/download and verify `ollama --version` works.
2. Pull a local Qwen model, for example `ollama pull qwen2.5:7b`.
3. Copy `.env.example` to `.env` in `apps/api` or the repo root and set `ENABLE_OLLAMA=true`.
4. Optionally set `OLLAMA_DEFAULT_MODEL=qwen2.5:7b` or another local Qwen tag you pulled.
5. Start the API and send requests to `/chat`; OMNIRA will route internally but call Ollama through `OLLAMA_BASE_URL`.

### Add a model

1. Add a base or OMNIRA entry in `models/registry`.
2. Add a model card in `models/model-cards`.
3. Add or update a provider adapter in `apps/api/app/models`.

### Add an agent

1. Add the agent profile in `apps/api/app/agents/service.py`.
2. Add a folder under `agents/` for prompts, configs, and docs.
3. Update routing rules in `apps/api/app/models/router.py` if the agent should be auto-selected.

## Architecture Principles

- Keep architecture modular.
- Avoid hardcoding one provider.
- Support local-first development.
- Use clean interfaces for models, memory, agents, tools, and RAG.
- Keep risky actions behind safety and approval boundaries.
- Build a working MVP before deeper optimization.

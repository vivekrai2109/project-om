# OMNIRA API

OMNIRA API is the FastAPI backend for OMNIRA Core. It exposes MVP endpoints for health, chat, model routing, memory, RAG, and agent execution.

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

## Test

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

## Notes

- Current storage is in-memory plus a JSON development file in `.data/memory.json`.
- TODO: move memory records to PostgreSQL.
- TODO: move vector retrieval to pgvector.
- Ollama integration is available when `ENABLE_OLLAMA=true` and a local model is running.
- TODO: add a first-class vLLM provider behind the current interfaces.

## Ollama Setup

```powershell
ollama pull qwen2.5:7b
ollama serve
```

Set these variables before starting the API:

```powershell
$env:ENABLE_OLLAMA = "true"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_DEFAULT_MODEL = "qwen2.5:7b"
$env:OLLAMA_FAST_MODEL = "qwen2.5:3b"
$env:OLLAMA_REASONING_MODEL = "qwen2.5:7b"
```

The API keeps OMNIRA model names for routing while mapping them to a local Qwen model for Ollama execution.

## Performance Tuning

OMNIRA now supports a fast local tier for personal-assistant traffic.

- `omnira-lite`, `omnira-bharat`, and `omnira-coach` can use `OLLAMA_FAST_MODEL` for lower latency.
- `omnira-prime` and `omnira-reasoning-qwen-7b-v0.1` use `OLLAMA_REASONING_MODEL` with a larger context and output budget.
- `omnira-code`, `omnira-platform`, `omnira-shield`, and `omnira-trade` use the default or family-specific 7B model path.
- `omnira-research` keeps a larger output budget because it is the slowest, analysis-heavy path.

Useful knobs:

```powershell
$env:OLLAMA_FAST_MODEL = "qwen2.5:3b"
$env:OLLAMA_KEEP_ALIVE = "20m"
$env:OLLAMA_DEFAULT_NUM_CTX = "4096"
$env:OLLAMA_FAST_NUM_CTX = "2048"
$env:OLLAMA_REASONING_NUM_CTX = "8192"
$env:OLLAMA_DEFAULT_MAX_TOKENS = "512"
$env:OLLAMA_FAST_MAX_TOKENS = "256"
$env:OLLAMA_REASONING_MAX_TOKENS = "1024"
$env:OLLAMA_RESEARCH_MAX_TOKENS = "768"
```

Recommended local setup:

```powershell
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
```

This gives OMNIRA a true fast path for personal assistance while keeping stronger reasoning capacity for code, platform, and research tasks.

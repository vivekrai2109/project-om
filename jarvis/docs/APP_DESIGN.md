# App Design (Low-Level)

## Orchestrator
- Builds prompt context.
- Calls model backend.
- Persists runs and memory summaries.
- Enforces retries and timeouts.

## Router
- Keyword-based selection (initial).
- Future: classifier-based routing.

## Planner
- Generates JSON plan for multi-step tasks.
- Executes steps sequentially with specialist agents.

## Memory
- Per-project memory summary in `data/memory/`.
- Run logs in `data/runs/`.

## Queue
- File-based queue in `data/queue/`.
- `enqueue` + worker processing.

## Web UI
- Chat-first UI with auto agent routing.
- Recent runs table and run details viewer.
- Queue status and stats panel.

## Model Backend
- OpenAI API or local vLLM.
- Configurable via `config.yaml`.
- Per-agent overrides via `models.yaml`.


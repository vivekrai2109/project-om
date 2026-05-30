# System Design (High-Level)

## Goals
- Centralized multi-agent system with specialist agents.
- Local-first development with Azure deployment target.
- Safe, auditable execution with clear observability.
- Open-weight model ownership (gpt-oss-20b) with OpenAI-compatible API.

## Core Components
- Client interfaces: Web UI, CLI, HTTP API.
- Orchestrator: task routing, plan generation, context building.
- Specialist agents: coder, infra, docs, monitor, planner, QA, security, release, research, data.
- Tool registry and permissions: allowed tools per agent.
- Memory and runs: project memory + run logs.
- Queue: background tasks and worker processing.
- Model backend: OpenAI API or local Azure-hosted gpt-oss-20b.

## Data Flow (High-Level)
- User submits task via UI or CLI.
- Orchestrator selects agent (auto) or uses requested agent.
- Context composed from repo snapshot + memory + task.
- Model response generated via backend (local or OpenAI).
- Response returned to UI and persisted to run logs.
- Optional: task queued and processed by worker.

## Reliability and Safety
- Retry and backoff for model calls.
- Tool permissions enforced by registry.
- Local-first storage for runs and memory.
- Backend health check to validate connectivity.

## Deployment Target (Azure)
- Azure GPU VM for vLLM serving gpt-oss-20b.
- Azure Container Apps or VM for Agent Hub service.
- Azure Storage for logs if needed.


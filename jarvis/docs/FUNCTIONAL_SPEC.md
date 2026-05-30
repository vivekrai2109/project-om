# Functional Specification

## Core User Stories
- As a user, I can submit a task via Web UI or CLI and receive a response.
- As a user, I can run multi-step plans with auto agent routing.
- As a user, I can review run history and outputs.
- As a user, I can queue background tasks.
- As a user, I can switch model backends (OpenAI or local).

## Non-Functional Requirements
- Low latency for single tasks.
- Reliable retries on transient failures.
- Safe tool execution with permissions.
- Traceable runs with logs.

## Success Criteria
- Task responses are consistent and reproducible.
- Runs are stored and searchable.
- Backend health check passes for configured model.


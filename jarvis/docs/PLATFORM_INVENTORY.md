# Platform Inventory

## Purpose

This document classifies the current Agent Hub modules by reuse value for Jarvis Lite.

## Reusable As-Is or With Small Changes
- `agenthub/orchestrator.py`: core task execution loop with memory and repo context
- `agenthub/workflows.py`: planner-driven task decomposition and execution
- `agenthub/router.py`: initial agent routing layer
- `agenthub/agents.py`: agent profile loading and selection
- `agenthub/config.py`: central runtime configuration
- `agenthub/models.py`: model selection and per-agent override support
- `agenthub/memory.py`: project memory and run persistence foundation
- `agenthub/tracing.py`: execution tracing and handoff instrumentation
- `agenthub/queue.py`: background task queue primitives
- `agenthub/backend.py`: backend connectivity checks
- `agenthub/tools.py`: tool registry loading and permission baseline

## Reusable But Needs Product Refactor
- `agenthub/cli.py`: usable foundation, but needs voice/session commands and better packaging checks
- `agenthub/web.py`: usable local control surface, but currently oriented to generic runs/proposals rather than Jarvis Lite sessions and approvals
- `agenthub/repo_health.py`: useful as one operator workflow, but too narrow as a product-facing capability
- `agenthub/propose.py`, `agenthub/apply_patch_cmd.py`, `agenthub/auto_apply.py`, `agenthub/approvals.py`: useful for supervised patch workflows, but should be reframed as approval-governed actions within a broader assistant product
- `agenthub/dataset.py`, `agenthub/evals.py`: valuable for quality loops, but internal platform features rather than first-wave user features

## New Product Modules Likely Needed
- voice capture and speech-to-text abstraction
- session management for interview practice and review
- approval policy engine for local actions
- audit history for user-visible action review
- coaching engine for question classification and answer scoring
- personal/work profile boundary management

## Product-Specific First Builds
- interview coach workflow
- voice command shell
- visible approval and action timeline
- personalized coaching memory and progress dashboards

## Immediate Stabilization Notes
- CLI startup should not require optional web dependencies at import time
- command documentation must stay aligned with the Typer command surface
- platform docs should distinguish reusable infrastructure from Jarvis Lite product features
- initial profile boundaries are now configured in `profiles.yaml`, but enforcement against tools and actions still needs to be wired into execution paths
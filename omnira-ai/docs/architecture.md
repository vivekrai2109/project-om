# Architecture

OMNIRA AI is organized as a modular monorepo.

## Core runtime

- OMNIRA Prime acts as the central orchestrator for mixed or complex requests.
- The model router classifies prompts using replaceable keyword rules and selects the best agent and model family.
- Agents encapsulate purpose, tool permissions, risk level, and system prompts.

## Memory and RAG

- OMNIRA Memory is split into conversation, personal, and project memory domains.
- The MVP uses JSON and in-memory stores behind interfaces so PostgreSQL can replace them later.
- RAG uses chunking, embedding, and vector search abstractions, with mock implementations for now and a planned pgvector backend later.

## Models and providers

- Model providers implement a shared `BaseModelProvider` interface.
- The first runtime path is provider-independent and can use mock responses today, Ollama next, and vLLM later.
- The model registry stores base-model mappings, OMNIRA model definitions, and deployment targets separately.

## Tools and safety

- Tool execution is policy-gated and disabled by default.
- Safety classifies actions into low, medium, high, and critical risk.
- Shell execution, Azure actions, Terraform apply, Kubernetes changes, destructive actions, and trading actions require approval.
- Defensive security learning is allowed; offensive or malicious usage is blocked.

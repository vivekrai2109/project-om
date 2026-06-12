# Model Strategy

Qwen is the primary base model family for OMNIRA AI because it provides a practical path for local experimentation, instruction tuning, and later self-hosted serving.

## Naming strategy

- 3B models target lightweight local assistance and fast routing defaults.
- 7B models target the main daily reasoning and specialist model layer.
- 14B models target deeper research and document-heavy tasks.
- 32B and larger tiers remain future options for higher-quality orchestration and cloud or self-hosted premium workloads.

## OMNIRA models

OMNIRA models are Qwen-derived fine-tuned models rather than scratch-trained models. The near-term path is:

1. Start with mock and provider adapters.
2. Support local Qwen variants through Ollama.
3. Fine-tune targeted OMNIRA models with QLoRA.
4. Merge and self-host selected models through vLLM.

## Reasoning-first priority

The first model that should become real is `omnira-reasoning-qwen-7b-v0.1`.

- It should power OMNIRA Prime orchestration and Jarvis self-development planning.
- It should be trained on planning, repo reasoning, tool-routing, approval-aware execution, and self-improvement traces.
- It should remain local-first through Ollama during bootstrap, then move to vLLM once the merged artifact is stable.

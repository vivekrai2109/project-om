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

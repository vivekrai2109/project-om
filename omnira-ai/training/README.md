# OMNIRA Lab

This directory contains training configs, scripts, and datasets for OMNIRA fine-tuning workflows.

## Current priority

The first production-worthy model target is `omnira-reasoning-qwen-7b-v0.1`.

It is intended to become the local reasoning tier for:
- OMNIRA Prime orchestration
- Jarvis self-development planning
- approval-aware code and workflow reasoning
- multi-step tool selection and repo diagnosis

## Training order

1. Build reasoning datasets from approved Jarvis and OMNIRA traces.
2. Run QLoRA on the Qwen 7B reasoning base.
3. Validate with code, platform, planning, and safety eval sets.
4. Merge the adapter and serve locally through Ollama or vLLM.

## Dataset buckets

- `instruction`: reasoning and task-solving exemplars
- `preference`: ranked outputs for better planning quality
- `eval`: fixed regression and quality benchmarks

Keep unsafe, speculative, or unapproved autonomous actions out of training data.

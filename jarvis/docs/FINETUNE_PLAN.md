# Tune Plan

This plan covers the first tuning path for your own Jarvis-focused model work, starting from `gpt-oss-20b`.

## Goal
- Strong code reasoning and safe changes
- Reliable infra guidance (CI/CD, containers, cloud)
- Consistent response style (concise, actionable)

## Frontend
- no direct frontend changes
- frontend benefits indirectly from better summaries, safer actions, and cleaner voice responses

## Backend
- export high-quality traces from local runs
- keep eval sets separate from training sets
- route tuned-model usage through the same backend abstraction as every other model

## Jarvis
- use approved runs, corrections, and reviews as supervised data
- keep policy, approval, and safety logic outside the model weights
- treat tuning as quality improvement, not as a replacement for governance

## Models
- start with `gpt-oss-20b`
- use LoRA or QLoRA first
- keep a stable base-model fallback

## Data
- Your own task history: successful runs + corrections
- Code review notes and bugfix diffs
- Infrastructure runbooks and postmortems

## Format
Each record should include:
- `system`: role + constraints
- `user`: task prompt
- `assistant`: ideal response

## Collect
1. Export high-quality runs from `data/runs/`.
2. Filter to "golden" examples (correct, concise, safe).
3. Add negative examples (bad answers + corrections) if available.

Tip: use `agenthub export-dataset --out data/finetune.jsonl`.

## Train
- Start with LoRA/QLoRA on gpt-oss-20b
- Iterate in small batches to reduce drift
- Keep a stable eval set that never trains

## Eval
- Use `evals/coding_infra_tasks.json` as a baseline
- Add project-specific tests and infra playbooks
- Track accuracy, brevity, and actionability

## Deploy
- Host the fine-tuned model on your Azure GPU VM
- Update `models.yaml` to point coder/infra agents to the fine-tuned model
- Keep a fallback to base gpt-oss-20b

# Fine-Tuning Plan (Coding + Infra)

This plan is for Path A (open-weight ownership) using gpt-oss-20b.

## Goals
- Strong code reasoning and safe changes
- Reliable infra guidance (CI/CD, containers, cloud)
- Consistent response style (concise, actionable)

## Data sources
- Your own task history: successful runs + corrections
- Code review notes and bugfix diffs
- Infrastructure runbooks and postmortems

## Data format (instruction style)
Each record should include:
- `system`: role + constraints
- `user`: task prompt
- `assistant`: ideal response

## Collection steps
1. Export high-quality runs from `data/runs/`.
2. Filter to "golden" examples (correct, concise, safe).
3. Add negative examples (bad answers + corrections) if available.

Tip: use `agenthub export-dataset --out data/finetune.jsonl`.

## Training approach
- Start with LoRA/QLoRA on gpt-oss-20b
- Iterate in small batches to reduce drift
- Keep a stable eval set that never trains

## Evaluation
- Use `evals/coding_infra_tasks.json` as a baseline
- Add project-specific tests and infra playbooks
- Track accuracy, brevity, and actionability

## Deployment
- Host the fine-tuned model on your Azure GPU VM
- Update `models.yaml` to point coder/infra agents to the fine-tuned model
- Keep a fallback to base gpt-oss-20b

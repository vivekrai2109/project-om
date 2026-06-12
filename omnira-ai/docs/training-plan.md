# Training Plan

The initial OMNIRA training plan focuses on fine-tuning, not pretraining.

## Near term

- Build instruction, preference, and eval datasets from high-signal workflows.
- Focus first on OMNIRA Reasoning 7B because Jarvis self-development, planning, and orchestration need a strong local reasoning tier before specialist expansion.
- Use QLoRA adapters to keep compute requirements practical.
- Use Jarvis learning records and training candidates as the first-party source for reasoning, approval, repo-diagnosis, and self-improvement data.

## Later

- Expand into OMNIRA Platform, Code, Research, and Bharat after the reasoning tier is stable.
- Add synthetic data only where it improves coverage without drifting from real user needs.
- Add quality gates for safety, tool behavior, and domain accuracy before releasing model versions.

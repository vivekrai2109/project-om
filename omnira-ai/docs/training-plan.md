# Training Plan

The initial OMNIRA training plan focuses on fine-tuning, not pretraining.

## Near term

- Build instruction, preference, and eval datasets from high-signal workflows.
- Focus first on OMNIRA Platform because platform operations, Azure, Terraform, Kubernetes, and CI/CD tasks are a clear specialist niche.
- Use QLoRA adapters to keep compute requirements practical.

## Later

- Expand into OMNIRA Code, Research, and Bharat.
- Add synthetic data only where it improves coverage without drifting from real user needs.
- Add quality gates for safety, tool behavior, and domain accuracy before releasing model versions.

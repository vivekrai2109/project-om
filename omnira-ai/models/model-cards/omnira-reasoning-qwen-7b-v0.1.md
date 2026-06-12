# OMNIRA Reasoning 7B v0.1

## Summary

OMNIRA Reasoning 7B v0.1 is the first dedicated local reasoning model for OMNIRA Prime and Jarvis self-development.

## Base family

- Derived from the Qwen family.
- Intended for QLoRA fine-tuning first, then merged local serving.

## Intended use

- Multi-step planning and orchestration.
- Jarvis self-development reasoning.
- Approval-aware tool and workflow selection.
- Repo analysis, diagnosis, and structured decision support.

## Notes

- Bootstrap runtime should use a local Qwen 7B model through Ollama.
- Promotion criteria should require passing code, planning, platform, and safety eval suites.
- This model replaces placeholder Prime routing with a real dedicated reasoning tier.
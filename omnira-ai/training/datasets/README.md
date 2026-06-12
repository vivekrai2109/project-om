# OMNIRA Dataset Layout

The reasoning training pipeline writes three dataset splits under this directory:

- `instruction/reasoning.jsonl`: supervised fine-tuning records with system, user, and assistant messages
- `preference/reasoning.jsonl`: chosen versus rejected pairs for preference optimization
- `eval/reasoning.jsonl`: held-out prompts and expected outputs for regression checks

## Source of truth

Datasets are generated from Jarvis artifacts in the sibling repo:

- `jarvis/data/training_candidates`
- `jarvis/data/learning`

Use the exporter:

```powershell
python training/scripts/prepare_dataset.py
```

For stricter curation:

```powershell
python training/scripts/prepare_dataset.py --require-approved --min-quality 0.8
```

Before training, run the preflight:

```powershell
python training/scripts/train_lora.py
```

That command validates the reasoning config and reports whether instruction, preference, and eval files are present.
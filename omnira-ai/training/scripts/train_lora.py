"""Preflight a QLoRA fine-tuning job for OMNIRA models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "training" / "configs" / "qlora-reasoning-7b.yaml"


def _parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if not normalized:
        return ""
    if normalized.lower() in {"true", "false"}:
        return normalized.lower() == "true"
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized.strip('"').strip("'")


def load_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key = ""
    current_container: dict[str, Any] | list[Any] | None = None
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("- "):
            if not isinstance(current_container, list):
                raise ValueError(f"List item without list context in {path}")
            current_container.append(_parse_scalar(stripped[2:]))
            continue

        if ":" not in stripped:
            raise ValueError(f"Unsupported YAML line in {path}: {raw_line}")

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        if indent == 0:
            current_key = key
            if value:
                data[key] = _parse_scalar(value)
                current_container = None
            else:
                next_content = ""
                for peek in lines[index + 1 :]:
                    candidate = peek.strip()
                    if not candidate or candidate.startswith("#"):
                        continue
                    next_content = candidate
                    break
                current_container = [] if next_content.startswith("- ") else {}
                data[key] = current_container
        else:
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            current_container = data[current_key]
            current_container[key] = _parse_scalar(value)

    return data


def summarize_training_job(config_path: Path) -> dict[str, Any]:
    config = load_simple_yaml(config_path)
    dataset_paths = {
        name: (REPO_ROOT / str(relative_path)).resolve()
        for name, relative_path in dict(config.get("dataset_paths") or {}).items()
    }
    dataset_files = {
        name: sorted(path.glob("*.jsonl")) if path.exists() else []
        for name, path in dataset_paths.items()
    }
    missing = [name for name, files in dataset_files.items() if not files]
    return {
        "job_name": config.get("job_name", "unknown"),
        "base_model": config.get("base_model", "unknown"),
        "strategy": config.get("strategy", "unknown"),
        "target_modules": list(config.get("target_modules") or []),
        "output_dir": str((REPO_ROOT / str(config.get("output_dir", "models/adapters"))).resolve()),
        "datasets": {name: [str(file) for file in files] for name, files in dataset_files.items()},
        "ready": not missing,
        "missing_datasets": missing,
        "recommended_next_step": (
            "Launch QLoRA fine-tuning with your preferred trainer once datasets are ready."
            if not missing
            else "Run prepare_dataset.py to generate the missing dataset splits before training."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight OMNIRA QLoRA training configuration.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize_training_job(args.config)
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

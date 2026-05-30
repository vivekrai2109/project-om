from __future__ import annotations

from pathlib import Path
import yaml

from .config import BASE_DIR

MODELS_PATH = BASE_DIR / "models.yaml"


def _load_models() -> dict:
    if not MODELS_PATH.exists():
        return {}
    return yaml.safe_load(MODELS_PATH.read_text(encoding="utf-8")) or {}


def get_model_for_agent(agent_name: str, fallback: str) -> str:
    data = _load_models()
    default = data.get("default", fallback)
    agents = data.get("agents", {}) or {}
    return str(agents.get(agent_name, default))

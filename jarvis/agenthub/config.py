from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


@dataclass(frozen=True)
class Config:
    model: str
    reasoning_effort: str
    max_output_tokens: int
    request_timeout_s: int
    retry_max_attempts: int
    retry_backoff_s: int
    backend: str
    base_url: str
    api_key_env: str
    tracing_enabled: bool
    tracing_sample_rate: float


def load_config(path: Path | None = None) -> Config:
    cfg_path = path or (BASE_DIR / "config.yaml")
    data = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    return Config(
        model=str(data.get("model", "gpt-5.2-codex")),
        reasoning_effort=str(data.get("reasoning_effort", "medium")),
        max_output_tokens=int(data.get("max_output_tokens", 1024)),
        request_timeout_s=int(data.get("request_timeout_s", 120)),
        retry_max_attempts=int(data.get("retry_max_attempts", 3)),
        retry_backoff_s=int(data.get("retry_backoff_s", 2)),
        backend=str(data.get("backend", "openai")),
        base_url=str(data.get("base_url", "")),
        api_key_env=str(data.get("api_key_env", "OPENAI_API_KEY")),
        tracing_enabled=bool((data.get("tracing") or {}).get("enabled", True)),
        tracing_sample_rate=float((data.get("tracing") or {}).get("sample_rate", 1.0)),
    )


def data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR

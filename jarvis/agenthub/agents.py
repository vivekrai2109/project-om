from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = BASE_DIR / "agents"


@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    system_prompt: str
    model: str | None = None
    allowed_tools: list[str] | None = None


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def list_agents() -> list[AgentProfile]:
    profiles: list[AgentProfile] = []
    for p in sorted(AGENTS_DIR.glob("*.yaml")):
        data = _load_yaml(p)
        profiles.append(
            AgentProfile(
                name=str(data.get("name", p.stem)),
                description=str(data.get("description", "")),
                system_prompt=str(data.get("system_prompt", "")),
                model=data.get("model"),
                allowed_tools=data.get("allowed_tools"),
            )
        )
    return profiles


def get_agent(name: str) -> AgentProfile:
    path = AGENTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise ValueError(f"Unknown agent: {name}")
    data = _load_yaml(path)
    return AgentProfile(
        name=str(data.get("name", name)),
        description=str(data.get("description", "")),
        system_prompt=str(data.get("system_prompt", "")),
        model=data.get("model"),
        allowed_tools=data.get("allowed_tools"),
    )

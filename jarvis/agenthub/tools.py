from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml

from .config import BASE_DIR
from .agents import AgentProfile

REGISTRY_PATH = BASE_DIR / "tools" / "registry.yaml"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: str
    default_allowed_agents: list[str]


def _load_registry() -> list[ToolSpec]:
    if not REGISTRY_PATH.exists():
        return []
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    tools = data.get("tools", [])
    specs: list[ToolSpec] = []
    for t in tools:
        specs.append(
            ToolSpec(
                name=str(t.get("name", "")),
                description=str(t.get("description", "")),
                risk=str(t.get("risk", "unknown")),
                default_allowed_agents=list(t.get("default_allowed_agents", [])),
            )
        )
    return specs


def list_tools() -> list[ToolSpec]:
    return _load_registry()


def is_tool_allowed(agent: AgentProfile, tool_name: str) -> bool:
    if agent.allowed_tools is not None:
        return tool_name in agent.allowed_tools

    for t in _load_registry():
        if t.name == tool_name:
            return agent.name in t.default_allowed_agents
    return False

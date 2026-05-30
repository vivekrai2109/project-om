from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml

from .config import BASE_DIR
from .tools import list_tools


PROFILES_PATH = BASE_DIR / "profiles.yaml"


@dataclass(frozen=True)
class ProfilePolicy:
    name: str
    description: str
    default_risk: str
    require_approval_for: list[str]
    allowed_paths: list[str]
    allowed_apps: list[str]
    allowed_commands: list[str]
    recording_requires_consent: bool


@dataclass(frozen=True)
class ToolDecision:
    profile: str
    tool: str
    tool_risk: str
    requires_approval: bool
    reason: str


@dataclass(frozen=True)
class AccessDecision:
    profile: str
    target: str
    allowed: bool
    reason: str


def _default_profiles() -> dict:
    return {
        "profiles": [
            {
                "name": "personal",
                "description": "Personal device usage with broader local workflow access.",
                "default_risk": "medium",
                "require_approval_for": ["shell", "fs_write", "web"],
                "allowed_paths": ["~/Documents", "~/Downloads", "~/Projects"],
                "allowed_apps": ["code", "browser", "terminal", "notes"],
                "allowed_commands": ["git status", "git diff", "python -m"],
                "recording_requires_consent": True,
            },
            {
                "name": "work",
                "description": "Work usage with tighter boundaries and explicit approval defaults.",
                "default_risk": "high",
                "require_approval_for": ["shell", "fs_write", "web", "git"],
                "allowed_paths": ["~/Work", "~/Projects"],
                "allowed_apps": ["code", "browser", "terminal"],
                "allowed_commands": ["git status", "git diff"],
                "recording_requires_consent": True,
            },
        ]
    }


def _load_policy_data() -> dict:
    if not PROFILES_PATH.exists():
        return _default_profiles()
    return yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8")) or _default_profiles()


def list_profiles() -> list[ProfilePolicy]:
    data = _load_policy_data()
    profiles = data.get("profiles", []) or []
    items: list[ProfilePolicy] = []
    for profile in profiles:
        items.append(
            ProfilePolicy(
                name=str(profile.get("name", "")),
                description=str(profile.get("description", "")),
                default_risk=str(profile.get("default_risk", "medium")),
                require_approval_for=list(profile.get("require_approval_for", [])),
                allowed_paths=list(profile.get("allowed_paths", [])),
                allowed_apps=list(profile.get("allowed_apps", [])),
                allowed_commands=list(profile.get("allowed_commands", [])),
                recording_requires_consent=bool(profile.get("recording_requires_consent", True)),
            )
        )
    return items


def get_profile(name: str) -> ProfilePolicy:
    for profile in list_profiles():
        if profile.name == name:
            return profile
    raise ValueError(f"Unknown profile: {name}")


def evaluate_tool_access(profile_name: str, tool_name: str) -> ToolDecision:
    profile = get_profile(profile_name)
    tool_specs = {tool.name: tool for tool in list_tools()}
    spec = tool_specs.get(tool_name)
    tool_risk = spec.risk if spec else profile.default_risk

    if tool_name in profile.require_approval_for:
        return ToolDecision(profile.name, tool_name, tool_risk, True, "profile requires explicit approval")

    if tool_risk == "high":
        return ToolDecision(profile.name, tool_name, tool_risk, True, "high-risk tool")

    return ToolDecision(profile.name, tool_name, tool_risk, False, "allowed by default profile policy")


def evaluate_path_access(profile_name: str, path_value: str) -> AccessDecision:
    profile = get_profile(profile_name)
    target = Path(path_value).expanduser().resolve()
    for allowed in profile.allowed_paths:
        allowed_path = Path(allowed).expanduser().resolve()
        if target == allowed_path or allowed_path in target.parents:
            return AccessDecision(profile.name, str(target), True, f"within allowed path {allowed}")
    return AccessDecision(profile.name, str(target), False, "path is outside allowed profile paths")


def evaluate_app_access(profile_name: str, app_name: str) -> AccessDecision:
    profile = get_profile(profile_name)
    if app_name in profile.allowed_apps:
        return AccessDecision(profile.name, app_name, True, "app is in the profile allowlist")
    return AccessDecision(profile.name, app_name, False, "app is not in the profile allowlist")


def evaluate_command_access(profile_name: str, command_text: str) -> AccessDecision:
    profile = get_profile(profile_name)
    for allowed in profile.allowed_commands:
        if command_text == allowed or command_text.startswith(allowed + " "):
            return AccessDecision(profile.name, command_text, True, f"matches allowed command prefix '{allowed}'")
    return AccessDecision(profile.name, command_text, False, "command is not in the profile allowlist")


def recording_requires_consent(profile_name: str) -> bool:
    return get_profile(profile_name).recording_requires_consent
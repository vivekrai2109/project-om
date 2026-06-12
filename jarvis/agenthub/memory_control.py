from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json

from .config import data_dir
from .knowledge_policy import (
    default_internet_learning_domains,
    internet_learning_scope_summary,
    normalize_compute_mode,
    normalize_internet_learning_domains,
    parse_compute_mode_command,
    parse_internet_learning_domain_command,
)
from .secure_storage import storage_encryption_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryControlState:
    memory_enabled: bool = True
    training_enabled: bool = True
    observation_enabled: bool = True
    profile_learning_enabled: bool = True
    internet_learning_enabled: bool = False
    internet_learning_domains: list[str] = field(default_factory=default_internet_learning_domains)
    compute_mode: str = "balanced"
    pinned_model: str = ""
    encryption_configured: bool = False
    encryption_mode: str = "not_configured"
    updated_at: str = ""
    updated_by: str = "system"
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _state_path() -> Path:
    path = data_dir() / "state" / "memory_control.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_memory_control_state() -> MemoryControlState:
    path = _state_path()
    encryption_configured, encryption_mode = storage_encryption_status()
    if not path.exists():
        return MemoryControlState(
            encryption_configured=encryption_configured,
            encryption_mode=encryption_mode,
            profile_learning_enabled=True,
            internet_learning_domains=default_internet_learning_domains(),
            compute_mode="balanced",
            pinned_model="",
            updated_at=_utc_now(),
            note="default local-first privacy policy",
        )
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return MemoryControlState(
        memory_enabled=bool(payload.get("memory_enabled", True)),
        training_enabled=bool(payload.get("training_enabled", True)),
        observation_enabled=bool(payload.get("observation_enabled", True)),
        profile_learning_enabled=bool(payload.get("profile_learning_enabled", True)),
        internet_learning_enabled=bool(payload.get("internet_learning_enabled", False)),
        internet_learning_domains=[str(item) for item in payload.get("internet_learning_domains", default_internet_learning_domains())],
        compute_mode=normalize_compute_mode(payload.get("compute_mode", "balanced")),
        pinned_model=str(payload.get("pinned_model", "") or ""),
        encryption_configured=encryption_configured,
        encryption_mode=encryption_mode,
        updated_at=str(payload.get("updated_at", "") or ""),
        updated_by=str(payload.get("updated_by", "system") or "system"),
        note=str(payload.get("note", "") or ""),
    )


def save_memory_control_state(state: MemoryControlState) -> MemoryControlState:
    path = _state_path()
    path.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
    return state


def set_memory_control_state(
    *,
    memory_enabled: bool | None = None,
    training_enabled: bool | None = None,
    observation_enabled: bool | None = None,
    profile_learning_enabled: bool | None = None,
    internet_learning_enabled: bool | None = None,
    internet_learning_domains: list[str] | None = None,
    compute_mode: str | None = None,
    pinned_model: str | None = None,
    updated_by: str = "owner",
    note: str = "",
) -> MemoryControlState:
    current = load_memory_control_state()
    next_state = MemoryControlState(
        memory_enabled=current.memory_enabled if memory_enabled is None else bool(memory_enabled),
        training_enabled=current.training_enabled if training_enabled is None else bool(training_enabled),
        observation_enabled=current.observation_enabled if observation_enabled is None else bool(observation_enabled),
        profile_learning_enabled=(current.profile_learning_enabled if profile_learning_enabled is None else bool(profile_learning_enabled)),
        internet_learning_enabled=(
            current.internet_learning_enabled if internet_learning_enabled is None else bool(internet_learning_enabled)
        ),
        internet_learning_domains=list(current.internet_learning_domains if internet_learning_domains is None else internet_learning_domains),
        compute_mode=normalize_compute_mode(current.compute_mode if compute_mode is None else compute_mode),
        pinned_model=current.pinned_model if pinned_model is None else str(pinned_model or "").strip(),
        encryption_configured=current.encryption_configured,
        encryption_mode=current.encryption_mode,
        updated_at=_utc_now(),
        updated_by=updated_by,
        note=note,
    )
    return save_memory_control_state(next_state)


def parse_memory_control_action(text: str) -> str | None:
    normalized = " ".join(str(text or "").strip().lower().split())
    if normalized in {"privacy status", "learning status", "memory status"}:
        return "status"
    if normalized.startswith(("don't remember this", "do not remember this", "dont remember this", "forget this")):
        return "exclude_current_turn"
    if normalized in {"stop remembering", "stop remembering things", "disable memory", "memory off"}:
        return "memory_off"
    if normalized in {"start remembering", "enable memory", "memory on"}:
        return "memory_on"
    if normalized in {"stop training on my data", "disable training on my data", "training off"}:
        return "training_off"
    if normalized in {"start training on my data", "enable training on my data", "training on"}:
        return "training_on"
    if normalized in {"stop recording what i do", "disable observation", "observation off"}:
        return "observation_off"
    if normalized in {"start recording what i do", "enable observation", "observation on"}:
        return "observation_on"
    if normalized in {"stop learning my profile", "disable profile learning", "profile learning off"}:
        return "profile_off"
    if normalized in {"start learning my profile", "enable profile learning", "profile learning on"}:
        return "profile_on"
    if normalized in {"enable internet learning", "internet learning on"}:
        return "internet_on"
    if normalized in {"disable internet learning", "internet learning off"}:
        return "internet_off"
    if normalized in {"unpin model", "clear pinned model"}:
        return "unpin_model"
    if parse_compute_mode_command(normalized):
        return "compute_mode"
    if parse_internet_learning_domain_command(normalized):
        return "internet_domains"
    if normalized.startswith(("pin model to ", "use only model ")):
        return "pin_model"
    return None


def parse_memory_control_details(text: str) -> dict[str, object]:
    compute_mode = parse_compute_mode_command(text)
    if compute_mode:
        return {"compute_mode": compute_mode}
    domain_update = parse_internet_learning_domain_command(text)
    if domain_update:
        operation, domains = domain_update
        return {"domain_operation": operation, "domains": domains}
    normalized = " ".join(str(text or "").strip().split())
    lowered = normalized.lower()
    for prefix in ("pin model to ", "use only model "):
        if lowered.startswith(prefix):
            return {"pinned_model": normalized[len(prefix) :].strip()}
    return {}


def apply_internet_learning_domain_update(state: MemoryControlState, operation: str, domains: list[str]) -> list[str]:
    requested = normalize_internet_learning_domains(domains)
    if operation == "set":
        return requested or list(state.internet_learning_domains)
    if operation == "add":
        return list(state.internet_learning_domains) + [item for item in requested if item not in state.internet_learning_domains]
    if operation == "remove":
        return [item for item in state.internet_learning_domains if item not in requested]
    return list(state.internet_learning_domains)


def should_skip_learning_capture(command_text: str, state: MemoryControlState) -> bool:
    normalized = " ".join(str(command_text or "").strip().lower().split())
    if not state.observation_enabled:
        return True
    return normalized.startswith(("don't remember this", "do not remember this", "dont remember this", "forget this"))


def should_create_training_candidate(intent_name: str, command_text: str, state: MemoryControlState) -> bool:
    if not state.training_enabled:
        return False
    lowered = str(command_text or "").lower()
    return intent_name in {"self_code_change", "self_improve_ui"} or "training" in lowered


def summarize_memory_control(state: MemoryControlState) -> tuple[str, dict[str, object]]:
    summary = (
        f"Memory is {'on' if state.memory_enabled else 'off'}. "
        f"Training on local traces is {'on' if state.training_enabled else 'off'}. "
        f"Observation capture is {'on' if state.observation_enabled else 'off'}. "
        f"Profile learning is {'on' if state.profile_learning_enabled else 'off'}. "
        f"Internet learning is {'on' if state.internet_learning_enabled else 'off'} for domains: {internet_learning_scope_summary(state.internet_learning_domains)}. "
        f"Compute mode is {state.compute_mode}. "
        f"Pinned model is {state.pinned_model or 'not set'}. "
        f"Encryption at rest is {'configured' if state.encryption_configured else 'not configured yet'}."
    )
    return summary, state.to_dict()
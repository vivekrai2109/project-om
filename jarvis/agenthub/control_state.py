from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from .config import data_dir
from .contracts import utc_timestamp


VALID_CONTROL_MODES = {"active", "paused", "stopped", "killed"}


@dataclass(slots=True)
class RuntimeControlState:
    mode: str = "active"
    updated_at: str = field(default_factory=utc_timestamp)
    source: str = "system"
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _state_dir() -> Path:
    path = data_dir() / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _state_dir() / "runtime_control.json"


def load_runtime_control_state() -> RuntimeControlState:
    path = _state_path()
    if not path.exists():
        state = RuntimeControlState()
        save_runtime_control_state(state)
        return state
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        state = RuntimeControlState(mode="active", source="system", note="state file unreadable, defaulted to active")
        save_runtime_control_state(state)
        return state
    mode = str(data.get("mode") or "active").lower()
    if mode not in VALID_CONTROL_MODES:
        mode = "active"
    return RuntimeControlState(
        mode=mode,
        updated_at=str(data.get("updated_at") or utc_timestamp()),
        source=str(data.get("source") or "system"),
        note=str(data.get("note") or ""),
    )


def save_runtime_control_state(state: RuntimeControlState) -> RuntimeControlState:
    path = _state_path()
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return state


def set_runtime_control_mode(mode: str, *, source: str = "system", note: str = "") -> RuntimeControlState:
    normalized = str(mode or "active").lower()
    if normalized in {"start", "resume"}:
        normalized = "active"
    if normalized not in VALID_CONTROL_MODES:
        raise ValueError(f"Unsupported control mode: {mode}")
    state = RuntimeControlState(mode=normalized, updated_at=utc_timestamp(), source=source, note=note)
    return save_runtime_control_state(state)
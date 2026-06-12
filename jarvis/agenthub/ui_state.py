from __future__ import annotations

UI_STATES: tuple[str, ...] = (
    "idle",
    "listening",
    "transcribing",
    "thinking",
    "speaking",
    "executing",
    "approval_required",
    "scanning",
    "memory_recall",
    "deployment_running",
    "alert",
    "danger",
    "warning",
    "muted",
    "disconnected",
    "error",
)

UI_MODES: tuple[str, ...] = (
    "presence",
    "conversation",
    "insight",
    "operations",
    "debug",
    "approval",
)

DEFAULT_UI_STATE = "idle"
DEFAULT_UI_MODE = "presence"


def normalize_ui_state(value: object, fallback: str = DEFAULT_UI_STATE) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in UI_STATES:
        return normalized
    return fallback


def normalize_ui_mode(value: object, fallback: str = DEFAULT_UI_MODE) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in UI_MODES:
        return normalized
    return fallback


def mode_shows_operations(mode: object) -> bool:
    return normalize_ui_mode(mode) in {"operations", "debug", "approval"}

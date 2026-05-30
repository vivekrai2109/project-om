from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


@dataclass(frozen=True)
class AssistantCoreResult:
    handled: bool
    message: str = ""
    mood: str = "idle"
    intent: str = ""


def handle_assistant_core(
    message: str,
    *,
    project_path: str,
    backend_status: str = "",
    backend_detail: str = "",
    active_model: str = "",
) -> AssistantCoreResult:
    normalized = " ".join(message.strip().split())
    if not normalized:
        return AssistantCoreResult(False)

    lowered = _strip_wake_word(normalized.lower())
    now = datetime.now()

    if _is_greeting(lowered):
        return AssistantCoreResult(
            True,
            _greeting_reply(lowered, now, project_path, backend_status),
            mood="speaking",
            intent="greeting",
        )

    if _is_time_request(lowered):
        return AssistantCoreResult(
            True,
            f"It is {now.strftime('%I:%M %p').lstrip('0')}.",
            mood="speaking",
            intent="time",
        )

    if _is_date_request(lowered):
        return AssistantCoreResult(
            True,
            f"Today is {now.strftime('%A, %d %B %Y')}.",
            mood="speaking",
            intent="date",
        )

    if _is_identity_request(lowered):
        return AssistantCoreResult(
            True,
            "I am Jarvis, your desktop assistant shell. I handle quick commands locally, route complex work to OMNIRA, and hold risky actions at approval gates.",
            mood="speaking",
            intent="identity",
        )

    if _is_location_request(lowered):
        project_name = Path(project_path).name or project_path
        return AssistantCoreResult(
            True,
            f"You are in the {project_name} workspace at {project_path}. {backend_status or 'The backend status is currently unknown.'}",
            mood="speaking",
            intent="location",
        )

    if _is_status_request(lowered):
        model_text = f" Active model lane: {active_model}." if active_model else ""
        detail_text = f" {backend_detail}" if backend_detail else ""
        return AssistantCoreResult(
            True,
            f"{backend_status or 'Jarvis is online.'}{model_text}{detail_text}",
            mood="speaking",
            intent="status",
        )

    return AssistantCoreResult(False)


def _strip_wake_word(value: str) -> str:
    return re.sub(r"^(jarvis)[,\s:;-]*", "", value, flags=re.IGNORECASE).strip()


def _is_greeting(value: str) -> bool:
    if value in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}:
        return True
    return value.startswith("hi ") or value.startswith("hello ") or value.startswith("good morning")


def _is_time_request(value: str) -> bool:
    patterns = (
        r"what(?:'s| is)? the time",
        r"tell me the time",
        r"current time",
        r"time now",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_date_request(value: str) -> bool:
    patterns = (
        r"what(?:'s| is)? the date",
        r"what day is it",
        r"today'?s date",
        r"what date is it",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_identity_request(value: str) -> bool:
    patterns = (
        r"who are you",
        r"what are you",
        r"introduce yourself",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_location_request(value: str) -> bool:
    patterns = (
        r"where am i",
        r"where are we",
        r"what project am i in",
        r"what workspace am i in",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_status_request(value: str) -> bool:
    patterns = (
        r"how are you",
        r"status",
        r"are you online",
        r"are you there",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _greeting_reply(value: str, now: datetime, project_path: str, backend_status: str) -> str:
    hour = now.hour
    if hour < 12:
        part_of_day = "morning"
    elif hour < 18:
        part_of_day = "afternoon"
    else:
        part_of_day = "evening"
    project_name = Path(project_path).name or "your workspace"
    if "good morning" in value:
        return f"Good morning. I am online in {project_name} and ready to help. {backend_status}".strip()
    if "good afternoon" in value:
        return f"Good afternoon. I am online in {project_name} and ready to help. {backend_status}".strip()
    if "good evening" in value:
        return f"Good evening. I am online in {project_name} and ready to help. {backend_status}".strip()
    return f"Good {part_of_day}. I am online in {project_name}. How can I help?"
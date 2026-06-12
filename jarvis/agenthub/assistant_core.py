from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


FAST_ROUTE_BLOCKERS = (
    "repo",
    "code",
    "bug",
    "fix",
    "implement",
    "refactor",
    "file",
    "folder",
    "directory",
    "search the web",
    "browser",
    "download",
    "open",
    "run",
    "execute",
    "terminal",
    "shell",
    "deploy",
    "azure",
    "docker",
    "kubernetes",
    "terraform",
    "pipeline",
    "research",
    "compare",
    "analyze",
    "plan",
    "architecture",
    "security",
    "vulnerability",
    "compliance",
)

FAST_ROUTE_PREFIXES = (
    "tell me",
    "explain",
    "what is",
    "what's",
    "who is",
    "who's",
    "can you",
    "could you",
    "please",
    "give me",
)


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

    lowered = _normalize_shell_phrase(_strip_wake_word(normalized.lower()))
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

    if _is_weather_request(lowered):
        return AssistantCoreResult(
            True,
            _weather_reply(lowered),
            mood="speaking",
            intent="weather",
        )

    if _is_capability_request(lowered):
        return AssistantCoreResult(
            True,
            "I can chat with you directly in this shell, report my backend and model status, summarize what I learned today, and route larger repo or system tasks into OMNIRA. Risky actions still stay behind approval gates.",
            mood="speaking",
            intent="capabilities",
        )

    if _is_listening_request(lowered):
        return AssistantCoreResult(
            True,
            "I can support voice workflows, but this terminal shell is still mainly a typed command surface. The live microphone loop exists in the voice stack and desktop bridge, not as a full always-listening terminal experience yet.",
            mood="speaking",
            intent="voice_capability",
        )

    if _is_vision_request(lowered):
        return AssistantCoreResult(
            True,
            "I do not have live camera perception inside this terminal shell yet. Camera consent and visual sensing belong to the desktop bridge path, so that part is not fully live here today.",
            mood="speaking",
            intent="vision_capability",
        )

    if _is_autonomy_request(lowered):
        return AssistantCoreResult(
            True,
            "My autonomy is supervised right now. I can plan, route tasks, record learning, create training candidates, and execute safer actions, but code changes and higher-risk operations are intentionally held behind approval gates.",
            mood="speaking",
            intent="autonomy_status",
        )

    if _is_understanding_request(lowered):
        return AssistantCoreResult(
            True,
            "Yes. I understand plain English reasonably well in this shell, but I am still a staged Jarvis build. Quick conversational turns are handled locally, while broader tasks route into OMNIRA or supervised workflows.",
            mood="speaking",
            intent="understanding_status",
        )

    return AssistantCoreResult(False)


def should_use_fast_assistant_route(message: str) -> bool:
    normalized = " ".join(message.strip().split())
    if not normalized:
        return False
    lowered = _normalize_shell_phrase(_strip_wake_word(normalized.lower()))
    if any(token in lowered for token in FAST_ROUTE_BLOCKERS):
        return False
    word_count = len(lowered.split())
    if _is_greeting(lowered) or _is_time_request(lowered) or _is_date_request(lowered):
        return True
    if _is_identity_request(lowered) or _is_status_request(lowered) or _is_weather_request(lowered):
        return True
    if _is_capability_request(lowered):
        return True
    if word_count <= 10 and lowered.endswith("?"):
        return True
    if word_count <= 14 and lowered.startswith(FAST_ROUTE_PREFIXES):
        return True
    return word_count <= 12


def _strip_wake_word(value: str) -> str:
    return re.sub(r"^(jarvis)[,\s:;-]*", "", value, flags=re.IGNORECASE).strip()


def _normalize_shell_phrase(value: str) -> str:
    normalized = " ".join(value.strip().split())
    replacements = {
        "hwo": "who",
        "waht": "what",
        "hwat": "what",
        "teh": "the",
        "yuo": "you",
        "wier": "wire",
        "lisen": "listen",
        "camra": "camera",
        "autnomy": "autonomy",
    }
    words = [replacements.get(word, word) for word in normalized.split()]
    return " ".join(words)


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


def _is_weather_request(value: str) -> bool:
    patterns = (
        r"weather",
        r"forecast",
        r"temperature",
        r"is it raining",
        r"will it rain",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_capability_request(value: str) -> bool:
    patterns = (
        r"what can you do",
        r"help me",
        r"how can you help",
        r"show capabilities",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_listening_request(value: str) -> bool:
    patterns = (
        r"can you hear me",
        r"can you listen",
        r"are you listening",
        r"microphone",
        r"voice mode",
        r"listen to me",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_vision_request(value: str) -> bool:
    patterns = (
        r"can you see me",
        r"camera",
        r"vision",
        r"watch me",
        r"look at me",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_autonomy_request(value: str) -> bool:
    patterns = (
        r"autonomy",
        r"autonomous",
        r"do stuff on your own",
        r"work on your own",
        r"why don't you do it yourself",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _is_understanding_request(value: str) -> bool:
    patterns = (
        r"do you understand me",
        r"can you understand me",
        r"do you understand",
        r"are you understanding me",
        r"do you get me",
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


def _weather_reply(value: str) -> str:
    location_match = re.search(r"(?:in|for)\s+([a-zA-Z][a-zA-Z\s.-]+)$", value, flags=re.IGNORECASE)
    if location_match:
        location = " ".join(location_match.group(1).split())
        return (
            f"I do not have a live weather service wired in yet, so I cannot verify the current weather for {location}. "
            f"I can add a weather tool next, or answer other desktop and project tasks right away."
        )
    return (
        "I do not have a live weather service wired in yet. Tell me a city if you want the question phrased clearly, "
        "or I can add a real weather tool so this becomes an instant structured answer."
    )
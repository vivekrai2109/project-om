from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .config import data_dir
from .router import pick_agent


VOICE_DIR = data_dir() / "voice"
LISTEN_STATE_PATH = VOICE_DIR / "listen_state.json"


@dataclass(frozen=True)
class VoiceRoute:
    transcript: str
    suggested_agent: str
    normalized_task: str
    wake_word: str
    mode: str


WAKE_WORD_MODE_MAP: dict[str, tuple[str, str]] = {
    "jarvis": ("jarvis", "assistant"),
    "hey jarvis": ("jarvis", "assistant"),
    "ok jarvis": ("jarvis", "assistant"),
    "okay jarvis": ("jarvis", "assistant"),
    "omnira": ("omnira", "architecture"),
    "hey omnira": ("omnira", "architecture"),
    "ok omnira": ("omnira", "architecture"),
    "okay omnira": ("omnira", "architecture"),
    "boss": ("boss", "personal"),
    "hey boss": ("boss", "personal"),
    "commander": ("commander", "operations"),
    "hey commander": ("commander", "operations"),
}


@dataclass(frozen=True)
class ListenState:
    enabled: bool
    mode: str


def route_transcript(transcript: str) -> VoiceRoute:
    wake_word, mode = detect_wake_word_mode(transcript)
    normalized = normalize_transcript_task(transcript)
    return VoiceRoute(
        transcript=transcript,
        suggested_agent=pick_agent(normalized),
        normalized_task=normalized,
        wake_word=wake_word,
        mode=mode,
    )


def normalize_transcript_task(transcript: str) -> str:
    normalized = " ".join(transcript.strip().split())
    return strip_wake_word(normalized)


def strip_wake_word(transcript: str) -> str:
    normalized = " ".join(transcript.strip().split())
    lowered = normalized.lower()
    for prefix in WAKE_WORD_MODE_MAP:
        if lowered == prefix:
            return ""
        if lowered.startswith(prefix + " "):
            return normalized[len(prefix):].strip(" ,:;-")
    return normalized


def detect_wake_word_mode(transcript: str) -> tuple[str, str]:
    lowered = " ".join(transcript.strip().lower().split())
    for prefix, mapping in WAKE_WORD_MODE_MAP.items():
        if lowered == prefix or lowered.startswith(prefix + " "):
            return mapping
    return ("", "assistant")


def live_listen_accepts_transcript(transcript: str) -> bool:
    lowered = " ".join(transcript.strip().lower().split())
    return any(lowered == prefix or lowered.startswith(prefix + " ") for prefix in WAKE_WORD_MODE_MAP)


def get_listen_state() -> ListenState:
    if not LISTEN_STATE_PATH.exists():
        return ListenState(enabled=False, mode="push-to-talk")
    data = json.loads(LISTEN_STATE_PATH.read_text(encoding="utf-8"))
    return ListenState(enabled=bool(data.get("enabled", False)), mode=str(data.get("mode", "push-to-talk")))


def set_listen_state(enabled: bool, mode: str | None = None) -> ListenState:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    current = get_listen_state()
    next_state = ListenState(enabled=enabled, mode=mode or current.mode)
    LISTEN_STATE_PATH.write_text(json.dumps(asdict(next_state), indent=2), encoding="utf-8")
    return next_state
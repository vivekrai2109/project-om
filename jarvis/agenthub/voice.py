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


@dataclass(frozen=True)
class ListenState:
    enabled: bool
    mode: str


def route_transcript(transcript: str) -> VoiceRoute:
    normalized = " ".join(transcript.strip().split())
    return VoiceRoute(
        transcript=transcript,
        suggested_agent=pick_agent(normalized),
        normalized_task=normalized,
    )


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
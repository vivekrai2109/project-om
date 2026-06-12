from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import json

from .ui_state import normalize_ui_state


@dataclass
class JarvisResponseEnvelope:
    reply_text: str
    speech_text: str
    state: str
    intent: str
    agent: str
    model: str
    provider: str
    confidence: float
    decision_path: list[str] = field(default_factory=list)
    memory_hits: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    workflow_trace: list[dict[str, str]] = field(default_factory=list)
    visualization: dict[str, Any] = field(default_factory=dict)
    safety_flags: list[str] = field(default_factory=list)
    approval_required: bool = False
    risk_level: str = "low"
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True)


def build_response_envelope(
    *,
    reply_text: str = "",
    speech_text: str | None = None,
    state: str = "idle",
    intent: str = "",
    agent: str = "",
    model: str = "",
    provider: str = "",
    confidence: float = 0.0,
    decision_path: list[str] | None = None,
    memory_hits: list[str] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    workflow_trace: list[dict[str, str]] | None = None,
    visualization: dict[str, Any] | None = None,
    safety_flags: list[str] | None = None,
    approval_required: bool = False,
    risk_level: str = "low",
    error: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> JarvisResponseEnvelope:
    normalized_reply = str(reply_text or "").strip()
    normalized_speech = normalized_reply if speech_text is None else str(speech_text or "").strip()
    normalized_confidence = max(0.0, min(1.0, float(confidence or 0.0)))
    return JarvisResponseEnvelope(
        reply_text=normalized_reply,
        speech_text=normalized_speech,
        state=normalize_ui_state(state),
        intent=str(intent or "").strip(),
        agent=str(agent or "").strip(),
        model=str(model or "").strip(),
        provider=str(provider or "").strip(),
        confidence=normalized_confidence,
        decision_path=list(decision_path or []),
        memory_hits=list(memory_hits or []),
        tool_calls=list(tool_calls or []),
        workflow_trace=list(workflow_trace or []),
        visualization=dict(visualization or {}),
        safety_flags=list(safety_flags or []),
        approval_required=bool(approval_required),
        risk_level=str(risk_level or "low").strip() or "low",
        error=error or None,
        metadata=dict(metadata or {}),
    )

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import data_dir
from .secure_storage import write_json_file


@dataclass
class InteractionRecord:
    timestamp: str
    project_id: str
    source: str
    ui_mode: str
    user_command: str
    transcript: str
    detected_intent: str
    selected_agent: str
    selected_model: str
    provider: str
    workflow_steps: list[dict[str, str]] = field(default_factory=list)
    reply_text: str = ""
    speech_text: str = ""
    user_feedback: str = ""
    memory_hits_count: int = 0
    tool_calls_count: int = 0
    success: bool = True
    memory_saved: bool = False
    training_candidate: bool = False
    approval_required: bool = False
    risk_level: str = "low"
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def write_interaction_record(project_id: str, record: InteractionRecord) -> Path:
    out_dir = data_dir() / "interactions" / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{stamp}-{uuid4().hex[:8]}.json"
    return write_json_file(out_path, asdict(record))

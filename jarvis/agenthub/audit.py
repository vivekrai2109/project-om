from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .config import data_dir


AUDIT_DIR = data_dir() / "audit"


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    action: str
    profile: str
    target: str
    outcome: str
    detail: str = ""


def append_audit_event(action: str, profile: str, target: str, outcome: str, detail: str = "") -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    event = AuditEvent(
        timestamp=ts,
        action=action,
        profile=profile,
        target=target,
        outcome=outcome,
        detail=detail,
    )
    path = AUDIT_DIR / f"{ts}_{action.replace(' ', '_')}.json"
    path.write_text(json.dumps(asdict(event), indent=2), encoding="utf-8")
    return path


def list_audit_events(limit: int = 20) -> list[AuditEvent]:
    if not AUDIT_DIR.exists():
        return []
    items: list[AuditEvent] = []
    files = sorted(AUDIT_DIR.glob("*.json"), reverse=True)
    for path in files[:limit]:
        data = json.loads(path.read_text(encoding="utf-8"))
        items.append(AuditEvent(**data))
    return items
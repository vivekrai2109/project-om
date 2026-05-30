from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .config import data_dir


PENDING_APPROVALS_PATH = data_dir() / "pending_approvals.json"


@dataclass(frozen=True)
class PendingApproval:
    id: str
    created_at: str
    task: str
    risk: str
    source: str
    note: str
    status: str
    resolved_at: str | None = None
    resolution_note: str | None = None


def _load_all() -> list[PendingApproval]:
    if not PENDING_APPROVALS_PATH.exists():
        return []
    data = json.loads(PENDING_APPROVALS_PATH.read_text(encoding="utf-8"))
    return [PendingApproval(**item) for item in data]


def _save_all(items: list[PendingApproval]) -> None:
    PENDING_APPROVALS_PATH.write_text(
        json.dumps([asdict(item) for item in items], indent=2),
        encoding="utf-8",
    )


def list_pending_approvals() -> list[PendingApproval]:
    return [item for item in _load_all() if item.status == "pending"]


def create_pending_approval(task: str, risk: str = "high", source: str = "desktop.cinematic", note: str = "") -> PendingApproval:
    approval = PendingApproval(
        id=str(uuid4()),
        created_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        task=" ".join(task.split()),
        risk=risk,
        source=source,
        note=note.strip(),
        status="pending",
    )
    items = _load_all()
    items.insert(0, approval)
    _save_all(items)
    return approval


def resolve_pending_approval(approval_id: str, decision: str, note: str = "") -> PendingApproval:
    if decision not in {"approved", "rejected"}:
        raise ValueError(f"Unsupported approval decision: {decision}")

    items = _load_all()
    resolved: PendingApproval | None = None
    next_items: list[PendingApproval] = []
    resolved_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for item in items:
        if item.id != approval_id:
            next_items.append(item)
            continue
        resolved = PendingApproval(
            id=item.id,
            created_at=item.created_at,
            task=item.task,
            risk=item.risk,
            source=item.source,
            note=item.note,
            status=decision,
            resolved_at=resolved_at,
            resolution_note=note.strip() or None,
        )
        next_items.append(resolved)

    if resolved is None:
        raise FileNotFoundError(f"pending approval not found: {approval_id}")

    _save_all(next_items)
    _write_history_record(resolved)
    return resolved


def _write_history_record(item: PendingApproval) -> Path:
    out_dir = data_dir() / "approvals"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = item.resolved_at or item.created_at
    out_path = out_dir / f"{stamp}_{item.id}.md"
    content = "\n".join(
        [
            f"# Approval Decision ({stamp})",
            f"- Approval ID: {item.id}",
            f"- Status: {item.status}",
            f"- Source: {item.source}",
            f"- Risk: {item.risk}",
            f"- Task: {item.task}",
            f"- Request Note: {item.note}",
            f"- Resolution Note: {item.resolution_note or ''}",
        ]
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path
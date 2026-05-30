from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .agents import get_agent
from .router import pick_agent
from .orchestrator import run_task
from .config import data_dir
from .tracing import start_trace, span, record_handoff


QUEUE_DIR = data_dir() / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
PROCESSING_DIR = QUEUE_DIR / "processing"
DONE_DIR = QUEUE_DIR / "done"
FAILED_DIR = QUEUE_DIR / "failed"


def _ensure_dirs() -> None:
    for d in (PENDING_DIR, PROCESSING_DIR, DONE_DIR, FAILED_DIR):
        d.mkdir(parents=True, exist_ok=True)


@dataclass
class QueueItem:
    id: str
    enqueued_at: str
    project_path: str
    agent: str
    task: str


@dataclass
class QueueResult:
    id: str
    enqueued_at: str
    completed_at: str
    project_path: str
    agent: str
    task: str
    output: str | None = None
    error: str | None = None


def enqueue(task: str, agent: str, project_path: str) -> Path:
    _ensure_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    item = QueueItem(
        id=str(uuid4()),
        enqueued_at=ts,
        project_path=project_path,
        agent=agent,
        task=task,
    )
    path = PENDING_DIR / f"{ts}_{item.id}.json"
    path.write_text(json.dumps(asdict(item), indent=2), encoding="utf-8")
    return path


def _pending_items() -> list[Path]:
    _ensure_dirs()
    return sorted(PENDING_DIR.glob("*.json"))


def claim_next() -> Path | None:
    items = _pending_items()
    if not items:
        return None
    src = items[0]
    dst = PROCESSING_DIR / src.name
    os.replace(src, dst)
    return dst


def process_item(path: Path) -> Path:
    _ensure_dirs()
    data = json.loads(path.read_text(encoding="utf-8"))
    item = QueueItem(**data)

    trace = start_trace(item.project_path, agent=item.agent if item.agent != "auto" else None, source="queue.worker")
    with span(trace, "queue.process", {"item_id": item.id}):
        agent_name = item.agent
        if agent_name == "auto":
            with span(trace, "router.pick", {"mode": "keyword"}):
                agent_name = pick_agent(item.task)
            record_handoff(trace, "auto", agent_name, "router.pick", task=item.task)

        try:
            output = run_task(item.task, get_agent(agent_name), item.project_path, trace=trace, source="queue.worker")
            result = QueueResult(
                id=item.id,
                enqueued_at=item.enqueued_at,
                completed_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                project_path=item.project_path,
                agent=agent_name,
                task=item.task,
                output=output,
            )
            out_path = DONE_DIR / path.name
            out_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
            os.replace(path, PROCESSING_DIR / (path.name + ".processed"))
            return out_path
        except Exception as exc:
            result = QueueResult(
                id=item.id,
                enqueued_at=item.enqueued_at,
                completed_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                project_path=item.project_path,
                agent=agent_name,
                task=item.task,
                error=str(exc),
            )
            out_path = FAILED_DIR / path.name
            out_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
            os.replace(path, PROCESSING_DIR / (path.name + ".failed"))
            return out_path


def queue_counts() -> dict[str, int]:
    _ensure_dirs()
    return {
        "pending": len(list(PENDING_DIR.glob("*.json"))),
        "processing": len(list(PROCESSING_DIR.glob("*.json"))),
        "done": len(list(DONE_DIR.glob("*.json"))),
        "failed": len(list(FAILED_DIR.glob("*.json"))),
    }

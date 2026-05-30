from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4
import json
import random
import time

from .config import load_config, data_dir
from .memory import project_id


@dataclass
class TraceContext:
    trace_id: str
    project_id: str
    project_path: str
    agent: str | None
    source: str | None
    output_path: Path
    stack: list[str] = field(default_factory=list)

    def write(self, record: dict[str, Any]) -> None:
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            with self.output_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            # Tracing should never break core flows.
            return


def _should_sample(sample_rate: float) -> bool:
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    return random.random() <= sample_rate


def start_trace(project_path: str, agent: str | None = None, source: str | None = None) -> TraceContext | None:
    cfg = load_config()
    if not cfg.tracing_enabled:
        return None
    if not _should_sample(cfg.tracing_sample_rate):
        return None

    pid = project_id(project_path)
    trace_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    out_dir = data_dir() / "traces" / pid
    out_path = out_dir / f"{trace_id}.jsonl"

    ctx = TraceContext(
        trace_id=trace_id,
        project_id=pid,
        project_path=project_path,
        agent=agent,
        source=source,
        output_path=out_path,
    )
    ctx.write(
        {
            "type": "trace_start",
            "trace_id": trace_id,
            "ts": time.time(),
            "project_id": pid,
            "project_path": project_path,
            "agent": agent,
            "source": source,
        }
    )
    return ctx


def event(ctx: TraceContext | None, name: str, attributes: dict[str, Any] | None = None) -> None:
    if ctx is None:
        return
    ctx.write(
        {
            "type": "event",
            "trace_id": ctx.trace_id,
            "name": name,
            "ts": time.time(),
            "attributes": attributes or {},
        }
    )


@contextmanager
def span(ctx: TraceContext | None, name: str, attributes: dict[str, Any] | None = None) -> Iterator[str | None]:
    if ctx is None:
        yield None
        return
    span_id = uuid4().hex[:12]
    parent_id = ctx.stack[-1] if ctx.stack else None
    ctx.stack.append(span_id)
    start_ts = time.time()
    status = "ok"
    error = None
    try:
        yield span_id
    except Exception as exc:
        status = "error"
        error = str(exc)
        raise
    finally:
        end_ts = time.time()
        if ctx.stack and ctx.stack[-1] == span_id:
            ctx.stack.pop()
        ctx.write(
            {
                "type": "span",
                "trace_id": ctx.trace_id,
                "span_id": span_id,
                "parent_id": parent_id,
                "name": name,
                "ts_start": start_ts,
                "ts_end": end_ts,
                "duration_ms": int((end_ts - start_ts) * 1000),
                "status": status,
                "error": error,
                "attributes": attributes or {},
            }
        )


def record_handoff(
    ctx: TraceContext | None,
    from_agent: str,
    to_agent: str,
    reason: str,
    task: str | None = None,
) -> None:
    if ctx is None:
        return
    event(
        ctx,
        "handoff",
        {
            "from": from_agent,
            "to": to_agent,
            "reason": reason,
            "task": task or "",
        },
    )

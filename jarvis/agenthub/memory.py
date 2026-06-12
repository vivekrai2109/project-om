from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
from datetime import datetime

from .config import data_dir
from .secure_storage import read_text_file, write_json_file, write_text_file


@dataclass
class RunRecord:
    timestamp: str
    project_path: str
    agent: str
    task: str
    response: str
    model: str
    trace_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


def project_id(project_path: str) -> str:
    h = hashlib.sha1(project_path.encode("utf-8")).hexdigest()
    return h[:12]


def memory_file(pid: str) -> Path:
    p = data_dir() / "memory" / f"{pid}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_memory(pid: str) -> str:
    p = memory_file(pid)
    return read_text_file(p, default="")


def append_memory(pid: str, text: str) -> None:
    p = memory_file(pid)
    if text.strip():
        existing = read_text_file(p, default="")
        write_text_file(p, existing + "\n" + text.strip() + "\n")


def write_run(pid: str, record: RunRecord) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = data_dir() / "runs" / pid
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}.json"
    return write_json_file(out_path, asdict(record))

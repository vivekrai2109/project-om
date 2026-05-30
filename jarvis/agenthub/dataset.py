from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import data_dir
from .agents import get_agent


def _iter_run_files() -> Iterable[Path]:
    runs_dir = data_dir() / "runs"
    if not runs_dir.exists():
        return []
    return runs_dir.glob("**/*.json")


def append_record(out_path: Path, system: str, user: str, assistant: str, meta: dict | None = None) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "system": system,
        "user": user,
        "assistant": assistant,
        "meta": meta or {},
    }
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def export_dataset(out_path: Path, project_path: str | None = None, min_chars: int = 40) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for p in _iter_run_files():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if project_path and data.get("project_path") != project_path:
                continue
            response = str(data.get("response", "")).strip()
            task = str(data.get("task", "")).strip()
            agent_name = str(data.get("agent", "")).strip() or "planner"
            if len(response) < min_chars or not task:
                continue

            try:
                agent = get_agent(agent_name)
                system = agent.system_prompt
            except Exception:
                system = "You are a helpful assistant."

            record = {
                "system": system,
                "user": task,
                "assistant": response,
                "meta": {
                    "agent": agent_name,
                    "model": data.get("model"),
                    "source": str(p),
                },
            }
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
            count += 1
    return count

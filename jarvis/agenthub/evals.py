from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .agents import get_agent
from .config import data_dir, BASE_DIR
from .orchestrator import run_task


@dataclass
class EvalResult:
    id: str
    agent: str
    task: str
    ok: bool
    missing: list[str]
    output: str


def _load_tasks(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _write_eval(results: list[EvalResult]) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = data_dir() / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}.json"
    payload = [asdict(r) for r in results]
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def run_golden_evals(project_path: str, task_file: Path | None = None) -> Path:
    path = task_file or (BASE_DIR / "evals" / "golden_tasks.json")
    tasks = _load_tasks(path)
    results: list[EvalResult] = []
    for t in tasks:
        agent_name = t.get("agent", "planner")
        task = t.get("task", "")
        expect = t.get("expect", [])
        output = run_task(task, get_agent(agent_name), project_path)

        text = output.lower()
        missing = [e for e in expect if e.lower() not in text]
        ok = len(missing) == 0

        results.append(
            EvalResult(
                id=str(t.get("id", "")),
                agent=agent_name,
                task=task,
                ok=ok,
                missing=missing,
                output=output,
            )
        )

    return _write_eval(results)

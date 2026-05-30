from __future__ import annotations

import json
from typing import Any

from .agents import get_agent
from .router import pick_agent
from .orchestrator import run_task
from .tracing import start_trace, span, record_handoff


PLAN_HINT = """
Create a task plan as JSON only. No prose.
Schema:
{
  "steps": [
    {"agent": "planner|coder|infra|docs|monitor|qa|security|release|research|data|auto",
     "task": "string"}
  ]
}
Keep steps minimal and executable.
"""


def _extract_json(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    # Try fenced JSON
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            if block.lstrip().startswith("json"):
                block = block.lstrip()[4:].strip()
            if block.strip().startswith("{") and block.strip().endswith("}"):
                return block.strip()
    # Fallback: first { ... last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def create_plan(task: str, project_path: str) -> list[dict[str, Any]]:
    planner = get_agent("planner")
    plan_task = f"{task.strip()}\n\n{PLAN_HINT.strip()}"
    output = run_task(plan_task, planner, project_path)

    raw = _extract_json(output)
    if not raw:
        return [{"agent": "auto", "task": task}]

    try:
        data = json.loads(raw)
        steps = data.get("steps", [])
        if isinstance(steps, list):
            norm = []
            for s in steps:
                agent = str(s.get("agent", "auto")).strip() or "auto"
                t = str(s.get("task", "")).strip()
                if t:
                    norm.append({"agent": agent, "task": t})
            return norm or [{"agent": "auto", "task": task}]
    except Exception:
        pass

    return [{"agent": "auto", "task": task}]


def run_plan(task: str, project_path: str) -> list[str]:
    steps = create_plan(task, project_path)
    outputs: list[str] = []
    trace = start_trace(project_path, agent="planner", source="run_plan")
    with span(trace, "plan.run", {"steps": len(steps)}):
        for idx, step in enumerate(steps, start=1):
            agent_name = step.get("agent", "auto")
            step_task = step.get("task", "")
            if not step_task:
                continue
            with span(trace, "plan.step", {"step": idx, "agent": agent_name}):
                if agent_name == "auto":
                    with span(trace, "router.pick", {"mode": "keyword"}):
                        agent_name = pick_agent(step_task)
                    record_handoff(trace, "auto", agent_name, "router.pick", task=step_task)
                agent = get_agent(agent_name)
                outputs.append(run_task(step_task, agent, project_path, trace=trace, source="run_plan"))
    return outputs

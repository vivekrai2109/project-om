from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import re

from .config import data_dir
from .dataset import append_record
from .agents import get_agent


@dataclass
class ApprovalResult:
    ok: bool
    message: str
    record_path: Path | None = None


def record_approval(proposal_id: str, project_path: str, note: str | None = None) -> ApprovalResult:
    proposals_dir = data_dir() / "proposals"
    summary_path = proposals_dir / f"{proposal_id}_summary.md"
    patch_path = proposals_dir / f"{proposal_id}.patch"
    raw_path = proposals_dir / f"{proposal_id}_raw.txt"

    if not summary_path.exists():
        return ApprovalResult(False, "proposal summary not found")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = data_dir() / "approvals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}_{proposal_id}.md"

    summary = summary_path.read_text(encoding="utf-8")
    patch = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""
    raw = raw_path.read_text(encoding="utf-8") if raw_path.exists() else ""

    content = "\n".join(
        [
            f"# Approval ({ts})",
            f"- Proposal: {proposal_id}",
            f"- Project: {project_path}",
            "",
            "## Summary",
            summary.strip(),
            "",
            "## Patch",
            "```diff",
            patch.strip(),
            "```",
            "",
            "## Raw Output",
            raw.strip(),
            "",
            "## Note",
            note or "",
        ]
    )

    out_path.write_text(content, encoding="utf-8")

    # Auto-append to finetune dataset
    agent_name = "planner"
    task = ""
    m_agent = re.search(r"- Agent:\s*(.+)", summary)
    m_task = re.search(r"- Task:\s*(.+)", summary)
    if m_agent:
        agent_name = m_agent.group(1).strip()
    if m_task:
        task = m_task.group(1).strip()

    try:
        agent = get_agent(agent_name)
        system = agent.system_prompt
    except Exception:
        system = "You are a helpful assistant."

    assistant = raw.strip() or summary.strip()
    user = task or "Approved proposal"
    dataset_path = data_dir() / "finetune.jsonl"
    append_record(
        dataset_path,
        system=system,
        user=user,
        assistant=assistant,
        meta={"agent": agent_name, "proposal_id": proposal_id, "project_path": project_path},
    )

    return ApprovalResult(True, "approval recorded and appended to dataset", out_path)

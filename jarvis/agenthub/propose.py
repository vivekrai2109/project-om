from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agents import AgentProfile, get_agent
from .router import pick_agent
from .orchestrator import run_task
from .backend import check_backend
from .config import load_config
from .config import data_dir


PROPOSE_INSTRUCTIONS = """
You are proposing changes only. Do NOT apply changes.
Return a short summary and a unified diff against the repo root.
Use relative file paths. Do not invent files that do not exist unless explicitly required.

OUTPUT FORMAT:
SUMMARY:
- <bullet list>
PATCH:
```diff
<unified diff>
```
""".strip()


@dataclass
class ProposalResult:
    summary_path: Path
    patch_path: Path
    raw_output_path: Path


def _parse_output(text: str) -> tuple[str, str]:
    summary = ""
    patch = ""
    if "PATCH:" in text:
        parts = text.split("PATCH:", 1)
        summary = parts[0].replace("SUMMARY:", "").strip()
        patch = parts[1].strip()
    else:
        summary = text.strip()
        patch = ""

    if "```" in patch:
        # Extract first fenced block
        blocks = patch.split("```")
        if len(blocks) >= 2:
            patch = blocks[1].strip()
            if patch.startswith("diff"):
                patch = patch[4:].strip()

    return summary.strip(), patch.strip()


def propose_fix(task: str, agent_name: str, project_path: str) -> ProposalResult:
    chosen = agent_name
    if agent_name == "auto":
        chosen = pick_agent(task)

    ok, msg = check_backend()
    if not ok:
        raise RuntimeError(f"Backend check failed: {msg}")

    cfg = load_config()
    if cfg.backend == "openai" and cfg.model.startswith("gpt-oss"):
        raise RuntimeError("OpenAI backend cannot use gpt-oss models. Switch backend to local or change model.")

    base_agent = get_agent(chosen)
    system_prompt = base_agent.system_prompt.strip() + "\n\n" + PROPOSE_INSTRUCTIONS
    agent = AgentProfile(
        name=base_agent.name,
        description=base_agent.description,
        system_prompt=system_prompt,
        model=base_agent.model,
        allowed_tools=base_agent.allowed_tools,
    )

    output = run_task(task, agent, project_path)
    summary, patch = _parse_output(output)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = data_dir() / "proposals"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / f"{ts}_raw.txt"
    raw_path.write_text(output, encoding="utf-8")

    summary_path = out_dir / f"{ts}_summary.md"
    summary_text = "\n".join(
        [
            f"# Proposal ({ts})",
            f"- Agent: {chosen}",
            f"- Task: {task}",
            "",
            "## Summary",
            summary or "(none)",
            "",
            "## Patch",
            f"{out_dir / f'{ts}.patch'}",
        ]
    )
    summary_path.write_text(summary_text, encoding="utf-8")

    patch_path = out_dir / f"{ts}.patch"
    patch_path.write_text(patch or "", encoding="utf-8")

    return ProposalResult(summary_path=summary_path, patch_path=patch_path, raw_output_path=raw_path)

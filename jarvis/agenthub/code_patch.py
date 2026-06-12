from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .apply_patch_cmd import apply_proposal
from .propose import propose_fix


@dataclass(slots=True)
class PatchProposalSummary:
    proposal_id: str
    summary_path: str
    patch_path: str
    raw_output_path: str
    diff_summary: str
    patch_preview: str
    validation_message: str = ""


class CodePatchEngine:
    def __init__(self, project_path: str) -> None:
        self._project_path = project_path

    def prepare_proposal(self, task: str, agent_name: str) -> PatchProposalSummary:
        proposal = propose_fix(task, agent_name, self._project_path)
        proposal_id = Path(proposal.patch_path).stem
        patch_text = Path(proposal.patch_path).read_text(encoding="utf-8")
        validation = apply_proposal(proposal_id, self._project_path, confirm=False)
        return PatchProposalSummary(
            proposal_id=proposal_id,
            summary_path=str(proposal.summary_path),
            patch_path=str(proposal.patch_path),
            raw_output_path=str(proposal.raw_output_path),
            diff_summary=self._diff_summary(patch_text),
            patch_preview=self._patch_preview(patch_text),
            validation_message=validation.message,
        )

    def _diff_summary(self, patch_text: str) -> str:
        files = 0
        additions = 0
        deletions = 0
        for line in patch_text.splitlines():
            if line.startswith("+++"):
                files += 1
            elif line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
        return f"files={files}, additions={additions}, deletions={deletions}"

    def _patch_preview(self, patch_text: str, *, max_lines: int = 30) -> str:
        lines = [line for line in patch_text.splitlines() if line.strip()]
        return "\n".join(lines[:max_lines])
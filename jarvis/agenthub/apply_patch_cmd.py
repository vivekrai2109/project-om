from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from .config import data_dir


@dataclass
class ApplyResult:
    ok: bool
    message: str


_PATH_RE = re.compile(r"^(?:---|\+\+\+)\s+([ab]/)?(.+)$")


def _validate_patch(patch_text: str) -> list[str]:
    errors: list[str] = []
    for line in patch_text.splitlines():
        m = _PATH_RE.match(line.strip())
        if not m:
            continue
        path = m.group(2)
        if path.startswith("/") or ":" in path:
            errors.append(f"absolute path not allowed: {path}")
        if ".." in path.split("/"):
            errors.append(f"parent path not allowed: {path}")
    return errors


def apply_proposal(proposal_id: str, project_path: str, confirm: bool) -> ApplyResult:
    proposals_dir = data_dir() / "proposals"
    patch_path = proposals_dir / f"{proposal_id}.patch"
    if not patch_path.exists():
        return ApplyResult(False, f"patch not found: {patch_path}")

    patch_text = patch_path.read_text(encoding="utf-8")
    if not patch_text.strip():
        return ApplyResult(False, "patch is empty")

    errors = _validate_patch(patch_text)
    if errors:
        return ApplyResult(False, "invalid patch:\n" + "\n".join(errors))

    cmd_check = ["git", "apply", "--check", str(patch_path)]
    cmd_apply = ["git", "apply", str(patch_path)]
    try:
        subprocess.run(cmd_check, cwd=project_path, check=True, capture_output=True, text=True)
    except Exception as exc:
        return ApplyResult(False, f"patch failed check: {exc}")

    if not confirm:
        return ApplyResult(True, "patch check passed (dry-run). Re-run with --confirm to apply.")

    try:
        subprocess.run(cmd_apply, cwd=project_path, check=True, capture_output=True, text=True)
        return ApplyResult(True, "patch applied successfully.")
    except Exception as exc:
        return ApplyResult(False, f"patch apply failed: {exc}")

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from .config import data_dir


@dataclass
class AutoApplyResult:
    ok: bool
    message: str


ALLOWED_EXTS = {".md", ".txt", ".rst"}
FORBIDDEN_EXTS = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml"}
_PATH_RE = re.compile(r"^(?:---|\+\+\+)\s+([ab]/)?(.+)$")


def _extract_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        m = _PATH_RE.match(line.strip())
        if not m:
            continue
        path = m.group(2)
        if path not in paths:
            paths.append(path)
    return paths


def _is_safe_path(path: str) -> bool:
    p = Path(path)
    if p.is_absolute():
        return False
    if ".." in p.parts:
        return False
    if p.suffix in FORBIDDEN_EXTS:
        return False
    if p.suffix in ALLOWED_EXTS:
        return True
    return False


def _validate_docs_only_patch(patch_path: Path) -> AutoApplyResult | None:
    patch_text = patch_path.read_text(encoding="utf-8")
    if not patch_text.strip():
        return AutoApplyResult(False, "patch is empty")

    paths = _extract_paths(patch_text)
    if not paths:
        return AutoApplyResult(False, "no file paths in patch")

    for p in paths:
        if not _is_safe_path(p):
            return AutoApplyResult(False, f"unsafe path for auto-apply: {p}")
    return None


def check_docs_only(proposal_id: str, project_path: str) -> AutoApplyResult:
    proposals_dir = data_dir() / "proposals"
    patch_path = proposals_dir / f"{proposal_id}.patch"
    if not patch_path.exists():
        return AutoApplyResult(False, f"patch not found: {patch_path}")

    invalid = _validate_docs_only_patch(patch_path)
    if invalid:
        return invalid

    cmd_check = ["git", "apply", "--check", str(patch_path)]
    try:
        subprocess.run(cmd_check, cwd=project_path, check=True, capture_output=True, text=True)
        return AutoApplyResult(True, "patch check passed (docs-only).")
    except Exception as exc:
        return AutoApplyResult(False, f"patch failed check: {exc}")


def auto_apply_docs_only(proposal_id: str, project_path: str) -> AutoApplyResult:
    proposals_dir = data_dir() / "proposals"
    patch_path = proposals_dir / f"{proposal_id}.patch"
    if not patch_path.exists():
        return AutoApplyResult(False, f"patch not found: {patch_path}")

    invalid = _validate_docs_only_patch(patch_path)
    if invalid:
        return invalid

    cmd_check = ["git", "apply", "--check", str(patch_path)]
    cmd_apply = ["git", "apply", str(patch_path)]
    try:
        subprocess.run(cmd_check, cwd=project_path, check=True, capture_output=True, text=True)
    except Exception as exc:
        return AutoApplyResult(False, f"patch failed check: {exc}")

    try:
        subprocess.run(cmd_apply, cwd=project_path, check=True, capture_output=True, text=True)
        return AutoApplyResult(True, "auto-applied (docs-only) successfully.")
    except Exception as exc:
        return AutoApplyResult(False, f"patch apply failed: {exc}")

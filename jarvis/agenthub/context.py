from __future__ import annotations

from pathlib import Path


def _safe_read(path: Path, max_chars: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        return ""


def _list_tree(root: Path, max_items: int = 40) -> list[str]:
    items: list[str] = []
    for p in sorted(root.iterdir()):
        if p.name.startswith("."):
            # include .env.example but skip other dotfiles by default
            if p.name != ".env.example":
                continue
        if p.name in {"data", ".venv", "__pycache__"}:
            continue
        suffix = "/" if p.is_dir() else ""
        items.append(p.name + suffix)
        if len(items) >= max_items:
            items.append("... (truncated)")
            break
    return items


REPO_CONTEXT_KEYWORDS = (
    "repo",
    "repository",
    "project",
    "code",
    "python",
    "typescript",
    "bug",
    "debug",
    "fix",
    "refactor",
    "implement",
    "file",
    "module",
    "folder",
    "directory",
    "readme",
    "test",
    "build",
    "deploy",
    "api",
)


def should_include_repo_context(task: str) -> bool:
    lowered = " ".join(task.lower().split())
    if not lowered:
        return False
    return any(keyword in lowered for keyword in REPO_CONTEXT_KEYWORDS)


def build_repo_context(project_path: str) -> str:
    root = Path(project_path)
    if not root.exists():
        return ""

    lines: list[str] = []
    lines.append(f"Project path: {root}")
    lines.append("Top-level:")
    for item in _list_tree(root):
        lines.append(f"- {item}")

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        lines.append("")
        lines.append("pyproject.toml (truncated):")
        lines.append(_safe_read(pyproject, max_chars=3000))

    readme = root / "README.md"
    if readme.exists():
        lines.append("")
        lines.append("README.md (truncated):")
        lines.append(_safe_read(readme, max_chars=2000))

    env_example = root / ".env.example"
    if env_example.exists():
        lines.append("")
        lines.append(".env.example (truncated):")
        lines.append(_safe_read(env_example, max_chars=1000))

    return "\n".join(lines).strip()

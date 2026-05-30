from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class RepoIssue:
    path: str
    line: int
    kind: str
    detail: str


PATTERNS = {
    "TODO": re.compile(r"\bTODO\b", re.IGNORECASE),
    "FIXME": re.compile(r"\bFIXME\b", re.IGNORECASE),
    "HACK": re.compile(r"\bHACK\b", re.IGNORECASE),
}


def scan_repo(root: Path) -> list[RepoIssue]:
    issues: list[RepoIssue] = []
    for path in root.rglob("*"):
        if path.is_dir():
            if path.name in {".git", ".venv", "__pycache__", "data"}:
                continue
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for kind, pat in PATTERNS.items():
                if pat.search(line):
                    issues.append(
                        RepoIssue(
                            path=str(path),
                            line=i,
                            kind=kind,
                            detail=line.strip()[:200],
                        )
                    )
    return issues

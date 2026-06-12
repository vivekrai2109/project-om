from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".pytest_cache",
    ".mypy_cache",
}

IGNORED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".pdf", ".pyc", ".pyo"}


@dataclass(slots=True)
class RepoScanSummary:
    root: str
    total_files: int
    categories: dict[str, int] = field(default_factory=dict)
    important_files: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    ui_files: list[str] = field(default_factory=list)
    backend_files: list[str] = field(default_factory=list)
    voice_files: list[str] = field(default_factory=list)
    omnira_adapter_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    architecture_summary: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ImpactReport:
    keyword: str
    files: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RepoIntelligence:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def scan_repo(self) -> RepoScanSummary:
        categories: dict[str, int] = {}
        important_files: list[str] = []
        entry_points: list[str] = []
        ui_files: list[str] = []
        backend_files: list[str] = []
        voice_files: list[str] = []
        omnira_adapter_files: list[str] = []
        test_files: list[str] = []
        total_files = 0

        for path in self._iter_files():
            total_files += 1
            relative = self._relative(path)
            category = self._categorize(relative)
            categories[category] = categories.get(category, 0) + 1
            if self._is_important(relative):
                important_files.append(relative)
            if self._is_entry_point(relative):
                entry_points.append(relative)
            if category == "ui":
                ui_files.append(relative)
            if category == "backend":
                backend_files.append(relative)
            if category == "voice":
                voice_files.append(relative)
            if category == "omnira_adapter":
                omnira_adapter_files.append(relative)
            if category == "tests":
                test_files.append(relative)

        return RepoScanSummary(
            root=str(self._root),
            total_files=total_files,
            categories=categories,
            important_files=sorted(important_files)[:40],
            entry_points=sorted(entry_points)[:20],
            ui_files=sorted(ui_files)[:20],
            backend_files=sorted(backend_files)[:20],
            voice_files=sorted(voice_files)[:20],
            omnira_adapter_files=sorted(omnira_adapter_files)[:20],
            test_files=sorted(test_files)[:20],
            architecture_summary=self._architecture_summary(categories, entry_points, ui_files, backend_files, voice_files, omnira_adapter_files),
        )

    def search_keyword(self, keyword: str, *, max_results: int = 25) -> list[dict[str, Any]]:
        normalized = str(keyword or "").strip().lower()
        matches: list[dict[str, Any]] = []
        for path in self._iter_files():
            relative = self._relative(path)
            if not normalized:
                matches.append({"path": relative, "line": 0, "preview": relative})
                if len(matches) >= max_results:
                    return matches
                continue
            if normalized in relative.lower():
                matches.append({"path": relative, "line": 0, "preview": relative})
                if len(matches) >= max_results:
                    return matches
                continue
            try:
                for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                    if normalized in line.lower():
                        matches.append({"path": relative, "line": line_no, "preview": line.strip()[:180]})
                        if len(matches) >= max_results:
                            return matches
                        break
            except Exception:
                continue
        return matches

    def impact_report(self, request_text: str) -> ImpactReport:
        lowered = str(request_text or "").lower()
        files: list[str] = []
        reasons: list[str] = []
        scan = self.scan_repo()

        def add(paths: list[str], reason: str) -> None:
            for item in paths:
                if item not in files:
                    files.append(item)
            if paths:
                reasons.append(reason)

        if any(token in lowered for token in ("ui", "qml", "presence", "visual", "dock", "orb")):
            add(scan.ui_files, "UI request touches cinematic shell and QML surfaces")
        if any(token in lowered for token in ("voice", "listen", "speech", "tts", "microphone", "wake")):
            add(scan.voice_files, "Voice request touches STT/TTS/listening pipeline")
        if any(token in lowered for token in ("backend", "omnira", "model", "provider", "response envelope")):
            add(scan.backend_files + scan.omnira_adapter_files, "Backend request touches runtime/backend adapter surfaces")
        if any(token in lowered for token in ("commander", "plan", "approval", "tool", "repo")):
            add(scan.important_files, "Control-plane request touches core commander files")
        if not files:
            files = list(scan.important_files[:12])
            reasons.append("General request mapped to important control-plane files")

        return ImpactReport(
            keyword=request_text,
            files=files[:20],
            reasons=reasons,
            summary=f"Identified {len(files[:20])} likely impacted files for the request.",
        )

    def _iter_files(self):
        for path in self._root.rglob("*"):
            if path.is_dir():
                continue
            if any(part in IGNORED_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() in IGNORED_SUFFIXES:
                continue
            yield path

    def _relative(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()

    def _categorize(self, relative: str) -> str:
        lowered = relative.lower()
        if lowered.endswith(".qml") or "/qml/" in lowered or "desktop" in lowered:
            return "ui"
        if any(token in lowered for token in ("voice", "speech", "tts", "listen")):
            return "voice"
        if any(token in lowered for token in ("backend_client", "backend.py", "omnira", "response_envelope")):
            return "omnira_adapter"
        if lowered.startswith("tests/") or "/tests/" in lowered or lowered.endswith("_test.py") or lowered.startswith("test_"):
            return "tests"
        if lowered.endswith(".py"):
            return "backend"
        if lowered.endswith(".md"):
            return "docs"
        return "other"

    def _is_important(self, relative: str) -> bool:
        lowered = relative.lower()
        important_tokens = (
            "desktop_qt.py",
            "commander.py",
            "runtime.py",
            "contracts.py",
            "response_envelope.py",
            "backend_client.py",
            "voice.py",
            "speech.py",
            "tts.py",
            "approval",
            "main.qml",
            "orchestrator.py",
            "main.py",
        )
        return any(token in lowered for token in important_tokens)

    def _is_entry_point(self, relative: str) -> bool:
        lowered = relative.lower()
        return lowered.endswith("__main__.py") or lowered.endswith("cli.py") or lowered.endswith("desktop_qt.py") or lowered.endswith("main.py")

    def _architecture_summary(
        self,
        categories: dict[str, int],
        entry_points: list[str],
        ui_files: list[str],
        backend_files: list[str],
        voice_files: list[str],
        omnira_adapter_files: list[str],
    ) -> list[str]:
        return [
            f"Scanned {sum(categories.values())} source files under {self._root.name}.",
            f"Entry points detected: {', '.join(sorted(entry_points)[:5]) or 'none'}.",
            f"UI surfaces: {len(ui_files)} file(s); backend/control surfaces: {len(backend_files)}; voice surfaces: {len(voice_files)}.",
            f"OMNIRA bridge surfaces: {len(omnira_adapter_files)} file(s).",
        ]
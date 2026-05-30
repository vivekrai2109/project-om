from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import time

from .repo_health import scan_repo
from .config import data_dir


def run_repo_health_once(project_path: str) -> Path:
    issues = scan_repo(Path(project_path))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = data_dir() / "health"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}.json"
    payload = [asdict(i) for i in issues]
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def schedule_repo_health(project_path: str, interval_s: int, once: bool = False) -> None:
    while True:
        out = run_repo_health_once(project_path)
        print(f"[health] wrote {out}")
        if once:
            return
        time.sleep(interval_s)


def _cleanup_dir(path: Path, older_than_days: int) -> int:
    if not path.exists():
        return 0
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - (older_than_days * 86400)
    removed = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except Exception:
                continue
    return removed


def run_maintenance_once(project_path: str, cleanup_days: int | None = None) -> dict:
    result = {}
    result["health_report"] = str(run_repo_health_once(project_path))

    if cleanup_days:
        base = data_dir()
        removed = 0
        removed += _cleanup_dir(base / "runs", cleanup_days)
        removed += _cleanup_dir(base / "health", cleanup_days)
        removed += _cleanup_dir(base / "proposals", cleanup_days)
        removed += _cleanup_dir(base / "approvals", cleanup_days)
        result["cleanup_removed_files"] = removed

    return result


def schedule_maintenance(project_path: str, interval_s: int, cleanup_days: int | None = None, once: bool = False) -> None:
    while True:
        result = run_maintenance_once(project_path, cleanup_days=cleanup_days)
        print(f"[maintenance] {result}")
        if once:
            return
        time.sleep(interval_s)

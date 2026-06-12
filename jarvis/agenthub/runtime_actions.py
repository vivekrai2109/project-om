from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from urllib.parse import quote_plus
from urllib.parse import urlparse
from urllib.request import urlopen

from .approval_queue import create_pending_approval, list_pending_approvals, resolve_pending_approval
from .config import data_dir, load_config
from .policies import evaluate_path_access, evaluate_tool_access


@dataclass(frozen=True)
class RuntimeActionResult:
    handled: bool
    message: str = ""
    action: str | None = None
    approval_id: str | None = None


def maybe_execute_runtime_action(
    task: str,
    project_path: str,
    profile: str = "personal",
    approve_runtime: bool = False,
    source: str = "cli.run",
    note: str = "",
    stage_approval: bool = True,
) -> RuntimeActionResult:
    normalized = " ".join(task.strip().split())
    if not normalized:
        return RuntimeActionResult(False)

    omnira_result = _maybe_handle_omnira_runtime_action(normalized, project_path)
    if omnira_result.handled:
        return omnira_result

    web_query = _match_web_search(normalized)
    if web_query:
        decision = evaluate_tool_access(profile, "web")
        if decision.requires_approval and not approve_runtime:
            return _stage_or_report_approval(normalized, decision.tool_risk, source, note, "web search", profile, "web-search", stage_approval)
        url = f"https://www.google.com/search?q={quote_plus(web_query)}"
        webbrowser.open(url)
        return RuntimeActionResult(True, f"Opened web search for: {web_query}\nURL: {url}", "web-search")

    open_target = _match_open_target(normalized)
    if open_target:
        target = _resolve_target(open_target, project_path)
        if _looks_like_url(open_target):
            decision = evaluate_tool_access(profile, "web")
            if decision.requires_approval and not approve_runtime:
                return _stage_or_report_approval(normalized, decision.tool_risk, source, note, "opening a web page", profile, "open-web", stage_approval)
            webbrowser.open(open_target)
            return RuntimeActionResult(True, f"Opened URL: {open_target}", "open-web")

        if not target.exists():
            return RuntimeActionResult(True, f"Target not found: {target}", "open-path")
        access = evaluate_path_access(profile, str(target))
        if not access.allowed:
            return RuntimeActionResult(True, f"Open blocked by profile policy: {access.reason}", "open-path")
        os.startfile(str(target))
        return RuntimeActionResult(True, f"Opened: {target}", "open-path")

    move_match = _match_move_file(normalized)
    if move_match:
        decision = evaluate_tool_access(profile, "fs_write")
        if decision.requires_approval and not approve_runtime:
            return _stage_or_report_approval(normalized, decision.tool_risk, source, note, "moving files", profile, "move-file", stage_approval)
        source = _resolve_target(move_match[0], project_path)
        destination = _resolve_target(move_match[1], project_path)
        if not source.exists():
            return RuntimeActionResult(True, f"Source not found: {source}", "move-file")
        source_access = evaluate_path_access(profile, str(source))
        destination_parent = destination.parent if destination.suffix else destination
        dest_access = evaluate_path_access(profile, str(destination_parent))
        if not source_access.allowed:
            return RuntimeActionResult(True, f"Move blocked by source policy: {source_access.reason}", "move-file")
        if not dest_access.allowed:
            return RuntimeActionResult(True, f"Move blocked by destination policy: {dest_access.reason}", "move-file")
        destination_parent.mkdir(parents=True, exist_ok=True)
        final_path = shutil.move(str(source), str(destination))
        return RuntimeActionResult(True, f"Moved file to: {final_path}", "move-file")

    file_query = _match_find_files(normalized)
    if file_query:
        root = Path(project_path)
        matches = _find_files(root, file_query)
        if not matches:
            return RuntimeActionResult(True, f"No files found for: {file_query}", "find-files")
        lines = [f"Found {len(matches)} file(s) for '{file_query}':"]
        for match in matches[:20]:
            lines.append(f"- {match}")
        if len(matches) > 20:
            lines.append("- ...")
        return RuntimeActionResult(True, "\n".join(lines), "find-files")

    return RuntimeActionResult(False)


def list_runtime_approvals() -> list[object]:
    return list_pending_approvals()


def approve_runtime_action(
    approval_id: str,
    project_path: str,
    profile: str = "personal",
    note: str = "",
) -> RuntimeActionResult:
    item = resolve_pending_approval(approval_id, "approved", note=note)
    result = maybe_execute_runtime_action(
        item.task,
        project_path,
        profile=profile,
        approve_runtime=True,
        source=f"approval:{item.source}",
        note=item.note,
        stage_approval=False,
    )
    if not result.handled:
        return RuntimeActionResult(True, f"Approval {item.id} marked approved, but no executable runtime action was recognized.", "approval")
    return RuntimeActionResult(True, f"Approval {item.id} approved.\n{result.message}", result.action, approval_id=item.id)


def reject_runtime_action(approval_id: str, note: str = "") -> RuntimeActionResult:
    item = resolve_pending_approval(approval_id, "rejected", note=note)
    return RuntimeActionResult(True, f"Approval {item.id} rejected for task: {item.task}", "approval", approval_id=item.id)


def _stage_or_report_approval(
    task: str,
    risk: str,
    source: str,
    note: str,
    action_label: str,
    profile: str,
    action: str,
    stage_approval: bool,
) -> RuntimeActionResult:
    if not stage_approval:
        return RuntimeActionResult(True, _approval_message(action_label, profile), action)
    approval = create_pending_approval(task, risk=risk, source=source, note=note)
    return RuntimeActionResult(True, _approval_message(action_label, profile, approval.id), action, approval_id=approval.id)


def _approval_message(action: str, profile: str, approval_id: str | None = None) -> str:
    if approval_id:
        return (
            f"Runtime action '{action}' requires approval under the '{profile}' profile. "
            f"Approval queued with id: {approval_id}."
        )
    return f"Runtime action '{action}' requires approval under the '{profile}' profile. Rerun with --approve-runtime to allow it."


def _match_web_search(task: str) -> str | None:
    patterns = (
        r"^(?:search web for|web search for|google)\s+(.+)$",
        r"^(?:search online for)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, task, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" \"'")
    return None


def _match_open_target(task: str) -> str | None:
    match = re.match(r"^open\s+(.+)$", task, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip(" \"'")


def _match_move_file(task: str) -> tuple[str, str] | None:
    match = re.match(r"^move\s+(.+?)\s+to\s+(.+)$", task, flags=re.IGNORECASE)
    if not match:
        return None
    return (match.group(1).strip(" \"'"), match.group(2).strip(" \"'"))


def _match_find_files(task: str) -> str | None:
    patterns = (
        r"^(?:find files? named|find file named|search files? for)\s+(.+)$",
        r"^(?:find)\s+(.+?)\s+(?:file|files)$",
    )
    for pattern in patterns:
        match = re.match(pattern, task, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" \"'")
    return None


def _looks_like_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://") or "." in lowered and " " not in lowered


def _resolve_target(value: str, project_path: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(project_path) / path
    return path.resolve()


def _find_files(root: Path, query: str) -> list[str]:
    lowered = query.lower()
    matches: list[str] = []
    for path in root.rglob("*"):
        if any(part.startswith(".") for part in path.parts):
            continue
        if path.is_file() and lowered in path.name.lower():
            matches.append(str(path))
    return sorted(matches)


def _maybe_handle_omnira_runtime_action(task: str, project_path: str) -> RuntimeActionResult:
    normalized = " ".join(task.strip().lower().split())
    if re.match(r"^start\s+omnira(\s+(backend|api|server))?$", normalized, flags=re.IGNORECASE):
        return _start_omnira_backend(project_path)
    if re.match(r"^stop\s+omnira(\s+(backend|api|server))?$", normalized, flags=re.IGNORECASE):
        return _stop_omnira_backend()
    if re.match(r"^restart\s+omnira(\s+(backend|api|server))?$", normalized, flags=re.IGNORECASE):
        stop_result = _stop_omnira_backend()
        start_result = _start_omnira_backend(project_path)
        return RuntimeActionResult(True, "\n".join([part for part in [stop_result.message, start_result.message] if part]), "omnira-restart")
    if re.match(r"^omnira(\s+backend)?\s+status$", normalized, flags=re.IGNORECASE):
        return _omnira_backend_status()
    return RuntimeActionResult(False)


def _omnira_runtime_state_path() -> Path:
    path = data_dir() / "state" / "omnira_runtime.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_omnira_runtime_state() -> dict[str, object]:
    path = _omnira_runtime_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_omnira_runtime_state(payload: dict[str, object]) -> None:
    _omnira_runtime_state_path().write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _clear_omnira_runtime_state() -> None:
    path = _omnira_runtime_state_path()
    if path.exists():
        path.unlink()


def _workspace_root(project_path: str) -> Path:
    project = Path(project_path).resolve()
    if project.name.lower() == "jarvis":
        return project.parent
    return project


def _omnira_api_dir(project_path: str) -> Path:
    return _workspace_root(project_path) / "omnira-ai" / "apps" / "api"


def _omnira_bind_settings() -> tuple[str, int, str]:
    cfg = load_config()
    parsed = urlparse(cfg.base_url or "http://127.0.0.1:8001")
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or (443 if scheme == "https" else 80))
    return host, port, f"{scheme}://{host}:{port}/health"


def _omnira_http_health() -> tuple[bool, str]:
    _, _, health_url = _omnira_bind_settings()
    try:
        with urlopen(health_url, timeout=5) as response:  # nosec B310 local owner-controlled health probe
            return response.status == 200, f"GET {health_url} -> {response.status}"
    except Exception as exc:
        return False, f"GET {health_url} failed: {exc}"


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, check=False)
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _start_omnira_backend(project_path: str) -> RuntimeActionResult:
    online, detail = _omnira_http_health()
    if online:
        return RuntimeActionResult(True, f"OMNIRA backend is already online. {detail}", "omnira-start")
    api_dir = _omnira_api_dir(project_path)
    if not api_dir.exists():
        return RuntimeActionResult(True, f"OMNIRA API directory not found: {api_dir}", "omnira-start")
    host, port, _ = _omnira_bind_settings()
    env = os.environ.copy()
    env.setdefault("ENABLE_OLLAMA", "false")
    pid = _launch_omnira_process(api_dir, host, port, env)
    _write_omnira_runtime_state(
        {
            "pid": pid,
            "host": host,
            "port": port,
            "api_dir": str(api_dir),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "started_by": "jarvis_runtime_action",
        }
    )
    for _ in range(10):
        time.sleep(0.3)
        online, detail = _omnira_http_health()
        if online:
            return RuntimeActionResult(True, f"Started OMNIRA backend on {host}:{port}. {detail}", "omnira-start")
    return RuntimeActionResult(True, f"Started OMNIRA backend process with pid {pid}. Health check is still pending.", "omnira-start")


def _launch_omnira_process(api_dir: Path, host: str, port: int, env: dict[str, str]) -> int:
    if os.name == "nt":
        command = (
            f"$env:ENABLE_OLLAMA='{env.get('ENABLE_OLLAMA', 'false')}'; "
            f"$p = Start-Process -FilePath '{sys.executable}' "
            f"-ArgumentList '-m','uvicorn','app.main:app','--host','{host}','--port','{port}' "
            f"-WorkingDirectory '{str(api_dir)}' -WindowStyle Hidden -PassThru; "
            "$p.Id"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=True,
        )
        return int((result.stdout or "").strip().splitlines()[-1])
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)],
        cwd=str(api_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return int(process.pid)


def _stop_omnira_backend() -> RuntimeActionResult:
    state = _read_omnira_runtime_state()
    pid = int(state.get("pid") or 0)
    if pid > 0 and _pid_is_running(pid):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False)
            else:
                os.kill(pid, 15)
        except Exception as exc:
            return RuntimeActionResult(True, f"Failed to stop OMNIRA backend pid {pid}: {exc}", "omnira-stop")
        _clear_omnira_runtime_state()
        return RuntimeActionResult(True, f"Stopped OMNIRA backend process {pid}.", "omnira-stop")
    online, detail = _omnira_http_health()
    if online:
        return RuntimeActionResult(True, f"OMNIRA backend is online but not tracked by Jarvis, so I did not force-stop it. {detail}", "omnira-stop")
    _clear_omnira_runtime_state()
    return RuntimeActionResult(True, "OMNIRA backend is already offline.", "omnira-stop")


def _omnira_backend_status() -> RuntimeActionResult:
    state = _read_omnira_runtime_state()
    online, detail = _omnira_http_health()
    pid = int(state.get("pid") or 0)
    pid_status = "running" if pid and _pid_is_running(pid) else "not tracked"
    host, port, _ = _omnira_bind_settings()
    lines = [
        f"OMNIRA backend is {'online' if online else 'offline'}.",
        f"Endpoint: {host}:{port}.",
        f"Tracked pid: {pid or 'none'} ({pid_status}).",
        f"Health: {detail}",
    ]
    if state.get("started_at"):
        lines.append(f"Started at: {state['started_at']}")
    return RuntimeActionResult(True, "\n".join(lines), "omnira-status")
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import webbrowser
from urllib.parse import quote_plus

from .approval_queue import create_pending_approval, list_pending_approvals, resolve_pending_approval
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
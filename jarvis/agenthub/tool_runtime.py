from __future__ import annotations

from pathlib import Path
import subprocess

from .backend import check_backend
from .backend_client import check_backend_connection
from .config import load_config
from .contracts import ToolRequest, ToolResult
from .policies import evaluate_command_access, evaluate_tool_access
from .repo_intelligence import RepoIntelligence


class SafeToolRuntime:
    def __init__(self, *, project_path: str, profile: str = "personal") -> None:
        self._project_path = str(Path(project_path).resolve())
        self._profile = profile
        self._repo = RepoIntelligence(self._project_path)

    def execute(self, request: ToolRequest) -> ToolResult:
        if request.tool_name in {
            "list_files",
            "read_file",
            "search_code",
            "inspect_repo",
            "git_status",
            "git_diff",
            "check_backend_health",
            "check_model_status",
        }:
            return self._execute_read_only(request)
        if request.tool_name in {
            "write_file_proposal",
            "apply_patch_proposal",
            "create_commit_proposal",
            "run_command_proposal",
        }:
            return self._execute_proposal(request)
        if request.tool_name in {"run_tests", "run_lint", "start_app_check", "compile_check"}:
            return self._execute_validation(request)
        return ToolResult(success=False, error=f"Unsupported tool: {request.tool_name}")

    def _execute_read_only(self, request: ToolRequest) -> ToolResult:
        if request.tool_name == "list_files":
            limit = int(request.args.get("limit", 50))
            files = [item["path"] for item in self._repo.search_keyword("", max_results=limit)]
            return ToolResult(success=True, output="\n".join(files[:limit]), metadata={"count": min(len(files), limit)})
        if request.tool_name == "read_file":
            relative_path = str(request.args.get("path", ""))
            path = (Path(self._project_path) / relative_path).resolve()
            if not path.exists() or not path.is_file():
                return ToolResult(success=False, error=f"File not found: {relative_path}")
            return ToolResult(success=True, output=path.read_text(encoding="utf-8", errors="ignore")[:4000], metadata={"path": relative_path})
        if request.tool_name == "search_code":
            query = str(request.args.get("query", "")).strip()
            matches = self._repo.search_keyword(query)
            return ToolResult(success=True, output="\n".join(f"{item['path']}:{item['line']} {item['preview']}" for item in matches), metadata={"matches": matches})
        if request.tool_name == "inspect_repo":
            scan = self._repo.scan_repo()
            return ToolResult(success=True, output="\n".join(scan.architecture_summary), metadata=scan.to_dict())
        if request.tool_name == "git_status":
            return self._run_command(["git", "status", "--short"], request.tool_name)
        if request.tool_name == "git_diff":
            return self._run_command(["git", "diff", "--stat"], request.tool_name)
        if request.tool_name == "check_backend_health":
            ok, detail = check_backend()
            return ToolResult(success=ok, output=detail, error="" if ok else detail, metadata={"backend_ok": ok})
        if request.tool_name == "check_model_status":
            cfg = load_config()
            ok, detail = check_backend_connection(cfg)
            return ToolResult(success=ok, output=f"backend={cfg.backend}; model={cfg.model}; {detail}", error="" if ok else detail)
        return ToolResult(success=False, error=f"Unsupported read-only tool: {request.tool_name}")

    def _execute_proposal(self, request: ToolRequest) -> ToolResult:
        decision = evaluate_tool_access(self._profile, "fs_write")
        return ToolResult(
            success=True,
            output=f"Prepared proposal for {request.tool_name}. Approval will be required before apply/commit execution.",
            diff_summary="proposal-only",
            metadata={
                "approval_required_before_apply": True,
                "dry_run": True,
                "policy_reason": decision.reason,
                "reason": request.reason,
                "args": dict(request.args),
            },
        )

    def _execute_validation(self, request: ToolRequest) -> ToolResult:
        if request.tool_name == "compile_check":
            targets = list(request.args.get("targets", [])) or ["agenthub\\contracts.py"]
            return self._run_command(["python", "-m", "py_compile", *targets], request.tool_name)
        if request.tool_name == "run_tests":
            target = str(request.args.get("target", "tests.test_commander_phase1_2"))
            return self._run_command(["python", "-m", "unittest", target], request.tool_name)
        if request.tool_name == "run_lint":
            return ToolResult(success=True, output="Lint placeholder ready. No linter is configured in this project yet.", metadata={"placeholder": True})
        if request.tool_name == "start_app_check":
            return ToolResult(success=True, output="App launch check should continue through the existing desktop/web startup path.", metadata={"placeholder": True})
        return ToolResult(success=False, error=f"Unsupported validation tool: {request.tool_name}")

    def _run_command(self, command: list[str], tool_name: str) -> ToolResult:
        command_text = " ".join(command)
        access = evaluate_command_access(self._profile, command_text)
        if not access.allowed and tool_name not in {"git_status", "git_diff", "run_tests", "compile_check"}:
            return ToolResult(success=False, error=access.reason, commands_run=[command_text])
        try:
            completed = subprocess.run(command, cwd=self._project_path, check=False, capture_output=True, text=True)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), commands_run=[command_text])
        output = (completed.stdout or completed.stderr or "").strip()
        return ToolResult(
            success=completed.returncode == 0,
            output=output,
            error="" if completed.returncode == 0 else output,
            commands_run=[command_text],
            verification=[tool_name],
        )
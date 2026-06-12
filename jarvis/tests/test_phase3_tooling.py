from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from agenthub.code_patch import PatchProposalSummary
from agenthub.commander import JarvisCommander
from agenthub.contracts import OwnerCommand, ToolRequest
from agenthub.repo_intelligence import RepoIntelligence
from agenthub.tool_runtime import SafeToolRuntime


class Phase3ToolingTests(TestCase):
    def test_repo_intelligence_finds_ui_and_backend_surfaces(self) -> None:
        repo = RepoIntelligence(Path.cwd())
        summary = repo.scan_repo()
        self.assertGreater(summary.total_files, 0)
        self.assertTrue(any(path.endswith("agenthub/desktop_qt.py") or path.endswith("agenthub/qml/Main.qml") for path in summary.important_files + summary.ui_files))

    def test_tool_runtime_inspect_repo_returns_summary(self) -> None:
        runtime = SafeToolRuntime(project_path=str(Path.cwd()))
        result = runtime.execute(ToolRequest(tool_name="inspect_repo", action="inspect"))
        self.assertTrue(result.success)
        self.assertIn("Entry points detected", result.output)

    def test_tool_runtime_validation_command_runs(self) -> None:
        runtime = SafeToolRuntime(project_path=str(Path.cwd()))
        result = runtime.execute(ToolRequest(tool_name="compile_check", action="validate", args={"targets": ["agenthub\\contracts.py", "agenthub\\commander.py"]}))
        self.assertTrue(result.success)

    @patch("agenthub.commander.CodePatchEngine.prepare_proposal")
    def test_commander_self_code_change_generates_supervised_proposal(self, mock_prepare) -> None:
        mock_prepare.return_value = PatchProposalSummary(
            proposal_id="prop-123",
            summary_path="summary.md",
            patch_path="patch.diff",
            raw_output_path="raw.txt",
            diff_summary="files=1, additions=3, deletions=1",
            patch_preview="+++ a/file.py",
            validation_message="patch check passed",
        )
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="Jarvis, recode yourself to improve the commander flow"))
        self.assertEqual(response.intent, "self_code_change")
        self.assertIn("self-code-change dry run", response.reply_text.lower())
        self.assertFalse(response.approval_required)
        self.assertTrue(response.metadata.get("apply_requires_approval"))

    @patch("agenthub.commander.CodePatchEngine.prepare_proposal")
    def test_commander_repo_analysis_is_real_local_flow(self, mock_prepare) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="inspect repo architecture summary for Jarvis UI and backend"))
        self.assertEqual(response.intent, "repo_analysis")
        self.assertEqual(response.agent, "repo_analyst")
        self.assertIn("Entry points detected", response.reply_text)
        mock_prepare.assert_not_called()
from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from agenthub.code_patch import PatchProposalSummary
from agenthub.commander import JarvisCommander
from agenthub.contracts import OwnerCommand


class Phase4WorkflowTests(TestCase):
    @patch("agenthub.commander.CodePatchEngine.prepare_proposal")
    def test_self_code_change_workflow_returns_dedicated_dry_run_payload(self, mock_prepare) -> None:
        mock_prepare.return_value = PatchProposalSummary(
            proposal_id="prop-self-code",
            summary_path="summary.md",
            patch_path="patch.diff",
            raw_output_path="raw.txt",
            diff_summary="files=2, additions=10, deletions=4",
            patch_preview="+++ a/agenthub/commander.py",
            validation_message="patch check passed",
        )
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="Jarvis, recode yourself to improve planning and backend structure"))
        self.assertEqual(response.intent, "self_code_change")
        self.assertEqual(response.metadata.get("workflow_type"), "self_code_change")
        self.assertIn("workflow_steps", response.metadata)
        self.assertIn("agent_tasks", response.metadata)
        self.assertGreaterEqual(len(response.metadata.get("agent_tasks", [])), 4)
        self.assertIn("validation_gates", response.metadata)
        self.assertIn("control_requirements", response.metadata)
        self.assertTrue(response.metadata.get("control_requirements", {}).get("owner_approval_required_before_apply"))
        self.assertIn("patch_proposal", response.metadata)
        self.assertIn("tests_to_run", response.metadata)
        self.assertTrue(response.metadata.get("apply_requires_approval"))
        self.assertIn("self-code-change dry run", response.reply_text.lower())

    @patch("agenthub.commander.CodePatchEngine.prepare_proposal")
    def test_self_improve_ui_workflow_returns_ui_protocol_payload(self, mock_prepare) -> None:
        mock_prepare.return_value = PatchProposalSummary(
            proposal_id="prop-self-ui",
            summary_path="summary.md",
            patch_path="patch.diff",
            raw_output_path="raw.txt",
            diff_summary="files=1, additions=12, deletions=2",
            patch_preview="+++ a/agenthub/qml/Main.qml",
            validation_message="patch check passed",
        )
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="Jarvis, improve UI readability and keep Presence minimal with better dock and orb focus"))
        self.assertEqual(response.intent, "self_improve_ui")
        self.assertEqual(response.metadata.get("workflow_type"), "self_improve_ui")
        self.assertIn("agent_tasks", response.metadata)
        self.assertGreaterEqual(len(response.metadata.get("agent_tasks", [])), 4)
        self.assertIn("validation_gates", response.metadata)
        self.assertIn("ui_protocol_rules", response.metadata)
        self.assertIn("design_changes", response.metadata)
        self.assertIn("before_after_notes", response.metadata)
        self.assertIn("self-ui-improvement dry run", response.reply_text.lower())

    @patch("agenthub.commander.CodePatchEngine.prepare_proposal")
    def test_self_ui_workflow_keeps_apply_under_approval_boundary(self, mock_prepare) -> None:
        mock_prepare.return_value = PatchProposalSummary(
            proposal_id="prop-self-ui-2",
            summary_path="summary.md",
            patch_path="patch.diff",
            raw_output_path="raw.txt",
            diff_summary="files=1, additions=8, deletions=1",
            patch_preview="+++ a/agenthub/qml/Main.qml",
            validation_message="patch check passed",
        )
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="self improve ui for presence mode"))
        self.assertFalse(response.approval_required)
        self.assertTrue(response.metadata.get("apply_requires_approval"))
        self.assertIn("Approval is required before applying UI changes", response.metadata.get("approval_requirement", ""))
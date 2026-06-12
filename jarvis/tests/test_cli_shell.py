from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agenthub.cli import _execute_shell_turn, _handle_shell_control_command
from agenthub.commander import JarvisCommander
from agenthub.memory_control import set_memory_control_state


class CliShellTests(unittest.TestCase):
    def setUp(self) -> None:
        set_memory_control_state(
            memory_enabled=True,
            training_enabled=True,
            observation_enabled=True,
            profile_learning_enabled=True,
            internet_learning_enabled=False,
            internet_learning_domains=["finance", "legal", "cloud", "networking", "coding_languages", "software_architecture", "security_defensive", "data_engineering", "systems_design"],
            compute_mode="balanced",
            pinned_model="",
            updated_by="test",
            note="cli shell test setup",
        )

    def test_shell_help_command_returns_usage(self) -> None:
        handled, should_continue, output = _handle_shell_control_command(
            "/help",
            project_path=str(Path.cwd()),
            policy_profile="personal",
        )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("/approve <id>", output)

    def test_shell_exit_command_stops_session(self) -> None:
        handled, should_continue, output = _handle_shell_control_command(
            "/exit",
            project_path=str(Path.cwd()),
            policy_profile="personal",
        )
        self.assertTrue(handled)
        self.assertFalse(should_continue)
        self.assertIn("Closing Jarvis shell", output)

    def test_shell_approvals_command_formats_queue(self) -> None:
        with patch("agenthub.cli.list_pending_approvals", return_value=[SimpleNamespace(id="approval-123", risk="high", source="jarvis.commander", task="apply patch")]):
            handled, should_continue, output = _handle_shell_control_command(
                "/approvals",
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("approval-123", output)

    def test_shell_status_command_reports_operating_state(self) -> None:
        with patch("agenthub.cli._format_operating_status", return_value="Jarvis operating status:\n- Backend: omnira."):
            handled, should_continue, output = _handle_shell_control_command(
                "/status",
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("Jarvis operating status", output)

    def test_shell_today_command_reports_learning_progress(self) -> None:
        with patch("agenthub.cli._format_daily_progress", return_value="Jarvis daily progress for 2026-06-12:\n- Interactions today: 4"):
            handled, should_continue, output = _handle_shell_control_command(
                "/today",
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("Jarvis daily progress", output)

    def test_shell_voice_command_reports_voice_status(self) -> None:
        with patch("agenthub.cli.get_listen_state", return_value=SimpleNamespace(enabled=True, mode="wake-word")), \
             patch("agenthub.cli.get_capture_state", return_value=SimpleNamespace(active=False, provider="windows_dictation", mode="idle")), \
             patch("agenthub.cli.speech_mode_status", return_value={"language_mode": "hinglish", "active_provider": "windows_dictation", "detail": "ready"}):
            handled, should_continue, output = _handle_shell_control_command(
                "/voice",
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("Jarvis voice status", output)
        self.assertIn("wake-word", output)

    def test_shell_omnira_command_reports_operator_status(self) -> None:
        with patch("agenthub.cli._format_omnira_status", return_value="OMNIRA operator status:\n- Provider: mock"):
            handled, should_continue, output = _handle_shell_control_command(
                "/omnira",
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("OMNIRA operator status", output)

    def test_shell_autonomy_command_reports_supervision_status(self) -> None:
        with patch("agenthub.cli._format_autonomy_status", return_value="Jarvis autonomy status:\n- Current autonomy mode: supervised"):
            handled, should_continue, output = _handle_shell_control_command(
                "/autonomy",
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("Current autonomy mode", output)

    def test_shell_listen_command_updates_listen_state(self) -> None:
        with patch("agenthub.cli.set_listen_state", return_value=SimpleNamespace(enabled=True, mode="push-to-talk")):
            handled, should_continue, output = _handle_shell_control_command(
                "/listen on",
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(handled)
        self.assertTrue(should_continue)
        self.assertIn("listen state is now on", output)

    def test_shell_turn_routes_to_jarvis_commander(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        should_continue, output = _execute_shell_turn(
            "privacy status",
            commander=commander,
            project_path=str(Path.cwd()),
            policy_profile="personal",
        )
        self.assertTrue(should_continue)
        self.assertIn("jarvis>", output)
        self.assertIn("Internet learning is off", output)

    def test_shell_turn_can_answer_operating_status_query_locally(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        with patch("agenthub.cli._format_operating_status", return_value="Jarvis operating status:\n- Own model path active: yes."):
            should_continue, output = _execute_shell_turn(
                "how are you operating",
                commander=commander,
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(should_continue)
        self.assertIn("Own model path active", output)

    def test_shell_turn_can_answer_daily_learning_query_locally(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        with patch("agenthub.cli._format_daily_progress", return_value="Jarvis daily progress for 2026-06-12:\n- Learning records written today: 3"):
            should_continue, output = _execute_shell_turn(
                "what did you learn today",
                commander=commander,
                project_path=str(Path.cwd()),
                policy_profile="personal",
            )
        self.assertTrue(should_continue)
        self.assertIn("Learning records written today", output)


if __name__ == "__main__":
    unittest.main()
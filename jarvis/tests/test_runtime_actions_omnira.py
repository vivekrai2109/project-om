from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from agenthub.runtime_actions import maybe_execute_runtime_action


class RuntimeActionsOmniraTests(unittest.TestCase):
    def test_omnira_status_reports_offline_without_runtime_state(self) -> None:
        with patch("agenthub.runtime_actions._omnira_http_health", return_value=(False, "offline for test")), patch(
            "agenthub.runtime_actions._read_omnira_runtime_state", return_value={}
        ):
            result = maybe_execute_runtime_action("omnira status", str(Path.cwd()))
        self.assertTrue(result.handled)
        self.assertEqual(result.action, "omnira-status")
        self.assertIn("offline", result.message.lower())

    def test_start_omnira_backend_starts_process_and_reports_online(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            api_dir = workspace / "omnira-ai" / "apps" / "api"
            api_dir.mkdir(parents=True)

            with patch("agenthub.runtime_actions._omnira_http_health", side_effect=[(False, "offline"), (True, "online")]), patch(
                "agenthub.runtime_actions._launch_omnira_process", return_value=4242
            ), patch("agenthub.runtime_actions._workspace_root", return_value=workspace), patch(
                "agenthub.runtime_actions._write_omnira_runtime_state"
            ) as write_state:
                result = maybe_execute_runtime_action("start omnira", str(workspace / "jarvis"))

        self.assertTrue(result.handled)
        self.assertEqual(result.action, "omnira-start")
        self.assertIn("Started OMNIRA backend", result.message)
        write_state.assert_called_once()
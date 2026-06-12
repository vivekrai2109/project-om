from __future__ import annotations

import json
from pathlib import Path
import unittest

from agenthub.contracts import OwnerCommand
from agenthub.desktop_qt import JarvisBridge
from agenthub.memory_control import set_memory_control_state


class DesktopQtCommanderTests(unittest.TestCase):
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
            note="desktop bridge test setup",
        )

    def test_bridge_applies_commander_response_to_ui_state(self) -> None:
        bridge = JarvisBridge()
        bridge._speaker_muted = True
        response = bridge._commander.handle_owner_command(
            OwnerCommand(
                text="privacy status",
                source="desktop_test",
                context={"ui_mode": bridge.uiMode, "surface": "desktop_qt_test"},
            )
        )

        bridge._handle_commander_response(response.to_json())

        self.assertIn("Internet learning is off", bridge.lastAssistantReply)
        self.assertIn("ROUTE //", bridge.routeSummary)
        self.assertIn("COMMAND", bridge.workflowStatus)
        self.assertEqual(bridge._response_envelope.intent, "privacy_status")

    def test_bridge_exposes_cockpit_summary(self) -> None:
        bridge = JarvisBridge()

        payload = json.loads(bridge.cockpitSummaryJson)

        self.assertIn("learning", payload)
        self.assertIn("voice", payload)
        self.assertIn("model_rationale", payload)
        self.assertTrue(bridge.showOperationsByDefault)

    def test_bridge_can_switch_speech_language_mode(self) -> None:
        bridge = JarvisBridge()

        bridge.setSpeechLanguageMode("hinglish")

        self.assertIn("HINGLISH", bridge.speechModeSummary)


if __name__ == "__main__":
    unittest.main()
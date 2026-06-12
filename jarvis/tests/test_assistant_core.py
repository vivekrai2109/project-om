from __future__ import annotations

import unittest

from agenthub.assistant_core import handle_assistant_core, should_use_fast_assistant_route


class AssistantCoreTests(unittest.TestCase):
    def test_typoed_identity_prompt_is_handled_locally(self) -> None:
        result = handle_assistant_core(
            "hwo are you",
            project_path="c:/Users/vivek.rai/Project-OM/jarvis",
        )
        self.assertTrue(result.handled)
        self.assertEqual(result.intent, "identity")
        self.assertIn("I am Jarvis", result.message)

    def test_autonomy_question_is_answered_locally(self) -> None:
        result = handle_assistant_core(
            "where is the autonomy of jarvis",
            project_path="c:/Users/vivek.rai/Project-OM/jarvis",
        )
        self.assertTrue(result.handled)
        self.assertEqual(result.intent, "autonomy_status")
        self.assertIn("approval gates", result.message)

    def test_voice_question_uses_fast_assistant_route(self) -> None:
        self.assertTrue(should_use_fast_assistant_route("can you hear me"))

    def test_understanding_question_is_answered_locally(self) -> None:
        result = handle_assistant_core(
            "Do you understand me",
            project_path="c:/Users/vivek.rai/Project-OM/jarvis",
        )
        self.assertTrue(result.handled)
        self.assertEqual(result.intent, "understanding_status")
        self.assertIn("I understand plain English", result.message)


if __name__ == "__main__":
    unittest.main()
from __future__ import annotations

import unittest

from agenthub.backend_client import build_routing_profile
from agenthub.config import Config
from agenthub.memory_control import set_memory_control_state


class BackendClientRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        set_memory_control_state(pinned_model="", compute_mode="balanced", updated_by="test", note="routing test setup")
        self.cfg = Config(
            model="gpt-5.2-codex",
            reasoning_effort="medium",
            max_output_tokens=1024,
            request_timeout_s=120,
            retry_max_attempts=3,
            retry_backoff_s=2,
            backend="omnira",
            base_url="http://localhost:8000",
            api_key_env="OPENAI_API_KEY",
            tracing_enabled=True,
            tracing_sample_rate=1.0,
        )

    def tearDown(self) -> None:
        set_memory_control_state(pinned_model="", compute_mode="balanced", updated_by="test", note="routing test cleanup")

    def test_lean_mode_prefers_small_models_and_lower_token_budget(self) -> None:
        profile = build_routing_profile("planner", None, self.cfg, dynamic_routing=False, compute_mode="lean")
        self.assertEqual(profile.model_name, "omnira-lite-qwen-3b-v0.1")
        self.assertEqual(profile.max_output_tokens, 384)
        self.assertEqual(profile.reasoning_effort, "low")

    def test_balanced_mode_preserves_reasoning_model_for_planner(self) -> None:
        profile = build_routing_profile("planner", None, self.cfg, dynamic_routing=False, compute_mode="balanced")
        self.assertEqual(profile.model_name, "omnira-reasoning-qwen-7b-v0.1")
        self.assertEqual(profile.max_output_tokens, 1024)
        self.assertEqual(profile.reasoning_effort, "medium")

    def test_performance_mode_uses_higher_budget(self) -> None:
        profile = build_routing_profile("research", None, self.cfg, dynamic_routing=False, compute_mode="performance")
        self.assertEqual(profile.model_name, "omnira-research-qwen-14b-v0.1")
        self.assertEqual(profile.max_output_tokens, 1536)
        self.assertEqual(profile.reasoning_effort, "high")

    def test_dynamic_routing_keeps_model_open_but_adjusts_budget(self) -> None:
        profile = build_routing_profile("planner", None, self.cfg, dynamic_routing=True, compute_mode="lean")
        self.assertIsNone(profile.model_name)
        self.assertEqual(profile.max_output_tokens, 384)
        self.assertEqual(profile.reasoning_effort, "low")

    def test_pinned_model_overrides_normal_agent_routing(self) -> None:
        set_memory_control_state(pinned_model="omnira-platform-qwen-7b-v0.1", updated_by="test", note="pin for routing test")
        profile = build_routing_profile("planner", None, self.cfg, dynamic_routing=False, compute_mode="balanced")
        self.assertEqual(profile.model_name, "omnira-platform-qwen-7b-v0.1")


if __name__ == "__main__":
    unittest.main()
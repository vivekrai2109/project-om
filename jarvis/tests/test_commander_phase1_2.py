from __future__ import annotations

from pathlib import Path
import unittest

from agenthub.backend_client import OMNIRA_MODEL_MAP
from agenthub.commander import JarvisCommander
from agenthub.control_state import set_runtime_control_mode
from agenthub.memory_control import load_memory_control_state, set_memory_control_state
from agenthub.contracts import OwnerCommand
from agenthub.events import LocalEventBus
from agenthub.runtime import JarvisRuntime


class CommanderPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        set_runtime_control_mode("active", source="test", note="reset before test")
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
            note="reset before test",
        )

    def tearDown(self) -> None:
        set_runtime_control_mode("active", source="test", note="reset after test")
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
            note="reset after test",
        )

    def test_event_bus_publish_and_history(self) -> None:
        bus = LocalEventBus(history_limit=5)
        seen: list[str] = []
        bus.subscribe("demo", lambda event: seen.append(event.payload["value"]))
        bus.publish("demo", {"value": "ok"}, correlation_id="cid-1", task_id="task-1")
        history = bus.history(event_type="demo")
        self.assertEqual(seen, ["ok"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].correlation_id, "cid-1")

    def test_commander_classifies_local_command(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        intent = commander.classify_intent("open operations", {})
        self.assertEqual(intent.intent, "open_operations")
        self.assertEqual(intent.local_command, "open operations")

    def test_commander_prepares_supervised_proposal_for_self_code_change(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        command = OwnerCommand(text="Jarvis, recode yourself to improve the backend safely")
        response = commander.handle_owner_command(command)
        self.assertFalse(response.approval_required)
        self.assertIn(response.risk_level, {"high", "critical"})
        self.assertEqual(response.state, "thinking")
        self.assertTrue(response.metadata.get("apply_requires_approval"))

    def test_runtime_heartbeat_reports_core_fields(self) -> None:
        runtime = JarvisRuntime(project_path=str(Path.cwd()))
        status = runtime.heartbeat()
        self.assertTrue(status.jarvis_alive)
        self.assertIsInstance(status.pending_approvals, int)
        self.assertIsInstance(status.warnings, list)

    def test_runtime_control_mode_persists_and_reports_blocked_state(self) -> None:
        runtime = JarvisRuntime(project_path=str(Path.cwd()))
        status = runtime.set_control_mode("paused", source="test", note="pause for test")
        self.assertEqual(status.control_mode, "paused")
        self.assertTrue(status.commands_blocked)

    def test_commander_blocks_self_code_change_when_runtime_is_killed(self) -> None:
        runtime = JarvisRuntime(project_path=str(Path.cwd()))
        runtime.set_control_mode("killed", source="test", note="kill for test")
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="Jarvis, recode yourself to improve the backend safely"))
        self.assertEqual(response.state, "warning")
        self.assertIn("Jarvis is killed", response.reply_text)

    def test_commander_accepts_start_command_after_runtime_is_killed(self) -> None:
        runtime = JarvisRuntime(project_path=str(Path.cwd()))
        runtime.set_control_mode("killed", source="test", note="kill for test")
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="start jarvis"))
        self.assertEqual(response.state, "speaking")
        self.assertIn("control mode set to active", response.reply_text.lower())

    def test_planner_maps_to_omnira_reasoning_model(self) -> None:
        self.assertEqual(OMNIRA_MODEL_MAP["planner"], "omnira-reasoning-qwen-7b-v0.1")

    def test_model_status_reports_routing_profile(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="model status"))
        self.assertEqual(response.intent, "model_status")
        self.assertIn("Compute mode: balanced", response.reply_text)
        self.assertIn("Resolved model:", response.reply_text)
        self.assertIn("Max output tokens:", response.reply_text)
        self.assertIn("model_rationale", response.metadata)
        self.assertIn("selected_model", response.metadata["model_rationale"])

    def test_memory_save_creates_learning_artifacts(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="remember this prefer concise summaries"))
        self.assertEqual(response.intent, "memory_save")
        self.assertIn("Saved to memory", response.reply_text)

    def test_privacy_status_reports_local_first_learning_controls(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="privacy status"))
        self.assertEqual(response.intent, "privacy_status")
        self.assertIn("Internet learning is off", response.reply_text)
        self.assertIn("Profile learning is on", response.reply_text)

    def test_memory_control_can_disable_training(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="stop training on my data"))
        self.assertEqual(response.intent, "memory_control")
        self.assertFalse(load_memory_control_state().training_enabled)
        self.assertIn("Training on local traces is off", response.reply_text)

    def test_memory_control_can_enable_internet_learning_for_safe_domains(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="enable internet learning"))
        self.assertEqual(response.intent, "memory_control")
        self.assertTrue(load_memory_control_state().internet_learning_enabled)
        self.assertIn("finance", response.reply_text)

    def test_memory_control_can_set_compute_mode(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="set compute mode to lean"))
        self.assertEqual(response.intent, "memory_control")
        self.assertEqual(load_memory_control_state().compute_mode, "lean")
        self.assertIn("Compute mode is lean", response.reply_text)

    def test_memory_control_can_pin_model(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="pin model to omnira-reasoning-qwen-7b-v0.1"))
        self.assertEqual(response.intent, "memory_control")
        self.assertEqual(load_memory_control_state().pinned_model, "omnira-reasoning-qwen-7b-v0.1")
        self.assertIn("Pinned model is omnira-reasoning-qwen-7b-v0.1", response.reply_text)

    def test_learning_readiness_reports_backend_and_counts(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="learning readiness"))
        self.assertEqual(response.intent, "learning_readiness")
        self.assertIn("Learning readiness is", response.reply_text)
        self.assertIn("Training candidates:", response.reply_text)

    def test_memory_control_can_set_internet_learning_domains(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="set internet learning domains to finance, cloud and coding"))
        self.assertEqual(response.intent, "memory_control")
        self.assertEqual(load_memory_control_state().internet_learning_domains, ["finance", "cloud", "coding_languages"])
        self.assertIn("finance, cloud, coding_languages", response.reply_text)

    def test_memory_control_can_remove_internet_learning_domain(self) -> None:
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="remove internet learning domain legal"))
        self.assertEqual(response.intent, "memory_control")
        self.assertNotIn("legal", load_memory_control_state().internet_learning_domains)
        self.assertIn("finance", response.reply_text)

    def test_memory_save_is_blocked_when_memory_is_disabled(self) -> None:
        set_memory_control_state(memory_enabled=False, updated_by="test", note="memory off for test")
        commander = JarvisCommander(project_path=str(Path.cwd()), stage_approvals=False)
        response = commander.handle_owner_command(OwnerCommand(text="remember this prefer concise summaries"))
        self.assertEqual(response.intent, "memory_save")
        self.assertIn("Memory capture is currently off", response.reply_text)


if __name__ == "__main__":
    unittest.main()
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agenthub.bridge_server import create_app
from agenthub.response_envelope import build_response_envelope
from agenthub.voice import live_listen_accepts_transcript, route_transcript


class VoiceWakeWordModeTests(unittest.TestCase):
    def test_route_transcript_maps_omnira_to_architecture_mode(self) -> None:
        route = route_transcript("Omnira review the platform architecture")
        self.assertEqual(route.mode, "architecture")
        self.assertEqual(route.wake_word, "omnira")
        self.assertEqual(route.normalized_task, "review the platform architecture")

    def test_route_transcript_maps_boss_to_personal_mode(self) -> None:
        route = route_transcript("hey boss remind me about my schedule")
        self.assertEqual(route.mode, "personal")
        self.assertEqual(route.wake_word, "boss")
        self.assertEqual(route.normalized_task, "remind me about my schedule")

    def test_live_listen_accepts_new_wake_words(self) -> None:
        self.assertTrue(live_listen_accepts_transcript("commander check production health"))
        self.assertTrue(live_listen_accepts_transcript("ok omnira explain the design"))


class BridgeServerContractTests(unittest.TestCase):
    def test_command_endpoint_returns_cinematic_contract(self) -> None:
        envelope = build_response_envelope(
            reply_text="AKS cluster health is stable.",
            speech_text="AKS cluster health is stable.",
            state="thinking",
            intent="general_conversation",
            agent="platform",
            model="omnira-platform-qwen-7b-v0.1",
            provider="omnira",
            confidence=0.82,
            approval_required=False,
            risk_level="low",
            workflow_trace=[{"step": "plan", "status": "ok", "detail": "Checking cluster health"}],
            tool_calls=[{"name": "kubectl.cluster.health", "status": "completed", "detail": "Read-only cluster probe"}],
            metadata={
                "plan": {"goal": "checking AKS cluster health"},
                "model_rationale": {"selected_model": "omnira-platform-qwen-7b-v0.1", "compute_mode": "balanced"},
            },
        )

        app = create_app(project_path=".", policy_profile="personal")
        with patch("agenthub.bridge_server.check_backend", return_value=(True, "ok")), \
             patch("agenthub.bridge_server.JarvisCommander.handle_owner_command", return_value=envelope), \
             patch("agenthub.bridge_server.list_pending_approvals", return_value=[]):
            client = TestClient(app)
            response = client.post("/api/v1/command", json={"message": "Commander check AKS cluster health", "conversation_id": "conv-1"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["conversation_id"], "conv-1")
        self.assertEqual(payload["state"], "thinking")
        self.assertEqual(payload["agent"], "platform")
        self.assertEqual(payload["model"], "omnira-platform-qwen-7b-v0.1")
        self.assertFalse(payload["requires_approval"])
        self.assertEqual(payload["memory_status"]["compute_mode"], "balanced")
        self.assertGreaterEqual(len(payload["tool_events"]), 1)

    def test_command_endpoint_returns_approval_contract(self) -> None:
        envelope = build_response_envelope(
            reply_text="Approval is required before I proceed.",
            speech_text="Approval is required before I proceed.",
            state="approval_required",
            intent="code_change",
            agent="coder",
            model="omnira-code-qwen-coder-7b-v0.1",
            provider="omnira",
            confidence=0.91,
            approval_required=True,
            risk_level="high",
            metadata={
                "approval_request": {
                    "approval_id": "approval-123",
                    "action_summary": "Apply infrastructure change",
                    "plan_summary": "Would modify deployment settings",
                    "expected_result": "Deployment settings updated",
                }
            },
        )

        app = create_app(project_path=".", policy_profile="personal")
        with patch("agenthub.bridge_server.check_backend", return_value=(True, "ok")), \
             patch("agenthub.bridge_server.JarvisCommander.handle_owner_command", return_value=envelope), \
             patch("agenthub.bridge_server.list_pending_approvals", return_value=[]):
            client = TestClient(app)
            response = client.post("/api/v1/command", json={"message": "deploy change", "conversation_id": "conv-2"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["requires_approval"])
        self.assertEqual(payload["approval"]["risk_level"], "high")
        self.assertEqual(payload["approval"]["approval_id"], "approval-123")
        self.assertIn("modify deployment settings", payload["approval"]["reason"])
        self.assertEqual(payload["approval"]["action_summary"], "Apply infrastructure change")

    def test_approve_endpoint_accepts_approval_id(self) -> None:
        app = create_app(project_path=".", policy_profile="personal")
        with patch("agenthub.bridge_server.approve_runtime_action") as approve_action:
            approve_action.return_value = type("ApproveResult", (), {"message": "approved", "action": "executed"})()
            client = TestClient(app)
            response = client.post("/api/v1/approvals/approve", json={"approval_id": "approval-321", "note": "ok"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["message"], "approved")

    def test_reject_endpoint_accepts_approval_id(self) -> None:
        app = create_app(project_path=".", policy_profile="personal")
        with patch("agenthub.bridge_server.reject_runtime_action") as reject_action:
            reject_action.return_value = type("RejectResult", (), {"message": "rejected", "action": "discarded"})()
            client = TestClient(app)
            response = client.post("/api/v1/approvals/reject", json={"approval_id": "approval-654", "note": "no"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["message"], "rejected")


if __name__ == "__main__":
    unittest.main()
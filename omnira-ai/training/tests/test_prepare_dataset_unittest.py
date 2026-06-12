from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
JARVIS_ROOT = WORKSPACE_ROOT / "jarvis"
OMNIRA_ROOT = WORKSPACE_ROOT / "omnira-ai"

if str(JARVIS_ROOT) not in sys.path:
    sys.path.insert(0, str(JARVIS_ROOT))
if str(OMNIRA_ROOT) not in sys.path:
    sys.path.insert(0, str(OMNIRA_ROOT))

from agenthub.secure_storage import write_json_file
from training.scripts.prepare_dataset import build_datasets


class PrepareDatasetTests(unittest.TestCase):
    def test_build_datasets_reads_encrypted_jarvis_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            learning = root / "learning"
            output = root / "datasets"
            candidates.mkdir()
            learning.mkdir()

            write_json_file(
                candidates / "candidate.json",
                {
                    "candidate_id": "train-enc-1",
                    "instruction": "Handle intent: self_code_change",
                    "input": "Improve planner safely",
                    "preferred_output": "Plan, validate, and require approval.",
                    "source_interaction_id": "learn-enc-1",
                    "quality_score": 0.91,
                    "approved_for_training": True,
                    "metadata": {"source": "encrypted-test"},
                },
            )
            write_json_file(
                learning / "learning.json",
                {
                    "record_id": "learn-enc-1",
                    "intent": "self_code_change",
                    "selected_agent": "architect",
                    "selected_model": "omnira-reasoning-qwen-7b-v0.1",
                    "files_touched": ["agenthub/commander.py"],
                    "tests_run": ["python -m unittest tests.test_commander_phase1_2"],
                    "success": True,
                    "result": {"success": True},
                },
            )

            counts = build_datasets(candidates, learning, output, min_quality=0.7, eval_ratio=0.0, require_approved=True)

            self.assertEqual(counts["prepared"], 1)
            self.assertEqual(counts["instruction"], 1)
            exported = (output / "instruction" / "reasoning.jsonl").read_text(encoding="utf-8")
            self.assertIn("Improve planner safely", exported)

    def test_build_datasets_preserves_richer_learning_context(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates"
            learning = root / "learning"
            output = root / "datasets"
            candidates.mkdir()
            learning.mkdir()

            write_json_file(
                candidates / "candidate.json",
                {
                    "candidate_id": "train-rich-1",
                    "instruction": "Handle intent: self_code_change Workflow: self_code_change Risk level: critical",
                    "input": "Refactor the planner safely",
                    "preferred_output": "Prepare a proposal, run validation, and require approval.",
                    "source_interaction_id": "learn-rich-1",
                    "quality_score": 0.95,
                    "approved_for_training": True,
                    "metadata": {
                        "workflow_name": "self_code_change",
                        "risk_level": "critical",
                        "owner_profile_signal": {"enabled": True, "explicit_preference": False},
                        "internet_learning_scope": {"enabled": True, "domains": ["finance", "cloud"], "safe_only": True},
                        "compute_hints": {"suggested_mode": "balanced"},
                    },
                },
            )
            write_json_file(
                learning / "learning.json",
                {
                    "record_id": "learn-rich-1",
                    "intent": "self_code_change",
                    "selected_agent": "architect",
                    "selected_model": "omnira-reasoning-qwen-7b-v0.1",
                    "files_touched": ["agenthub/commander.py"],
                    "tests_run": ["python -m unittest tests.test_commander_phase1_2"],
                    "success": True,
                    "result": {"success": True},
                },
            )

            build_datasets(candidates, learning, output, min_quality=0.7, eval_ratio=0.0, require_approved=True)

            exported = (output / "instruction" / "reasoning.jsonl").read_text(encoding="utf-8")
            self.assertIn("Context:", exported)
            self.assertIn("Internet learning scope", exported)
            self.assertIn("Compute hints", exported)


if __name__ == "__main__":
    unittest.main()
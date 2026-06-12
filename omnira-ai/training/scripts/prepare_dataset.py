"""Prepare instruction, preference, and eval datasets for OMNIRA fine-tuning."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
DEFAULT_CANDIDATES_DIR = WORKSPACE_ROOT / "jarvis" / "data" / "training_candidates"
DEFAULT_LEARNING_DIR = WORKSPACE_ROOT / "jarvis" / "data" / "learning"
DEFAULT_DATASETS_DIR = REPO_ROOT / "training" / "datasets"
JARVIS_ROOT = WORKSPACE_ROOT / "jarvis"

if str(JARVIS_ROOT) not in sys.path:
    sys.path.insert(0, str(JARVIS_ROOT))

try:
    from agenthub.secure_storage import iter_json_like_files, read_json_file
except Exception:
    def read_json_file(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.exists():
            return dict(default or {})
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def iter_json_like_files(root: Path) -> list[Path]:
        if not root.exists():
            return []
        plain = {path for path in root.rglob("*.json") if path.is_file() and not str(path).endswith(".json.enc")}
        encrypted = {path for path in root.rglob("*.json.enc") if path.is_file()}
        return sorted(plain | encrypted)


@dataclass(frozen=True)
class PreparedCandidate:
    candidate_id: str
    instruction: str
    input_text: str
    preferred_output: str
    rejected_output: str
    quality_score: float
    approved_for_training: bool
    source_interaction_id: str
    selected_model: str
    selected_agent: str
    intent: str
    success: bool
    files_touched: list[str]
    tests_run: list[str]
    metadata: dict[str, Any]


def _iter_json_files(path: Path) -> list[Path]:
    return iter_json_like_files(path)


def _learning_index(learning_dir: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in _iter_json_files(learning_dir):
        payload = read_json_file(path)
        record_id = str(payload.get("record_id") or "").strip()
        if record_id:
            index[record_id] = payload
    return index


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _build_candidate(payload: dict[str, Any], learning: dict[str, Any] | None) -> PreparedCandidate | None:
    instruction = _normalize_text(payload.get("instruction")) or "Solve the task carefully and produce the best approved response."
    input_text = _normalize_text(payload.get("input"))
    preferred_output = _normalize_text(payload.get("preferred_output"))
    if not input_text or not preferred_output:
        return None

    learning = learning or {}
    metadata = dict(payload.get("metadata") or {})
    result = learning.get("result") if isinstance(learning.get("result"), dict) else {}

    return PreparedCandidate(
        candidate_id=_normalize_text(payload.get("candidate_id")),
        instruction=instruction,
        input_text=input_text,
        preferred_output=preferred_output,
        rejected_output=_normalize_text(payload.get("rejected_output")),
        quality_score=_coerce_float(payload.get("quality_score"), 0.0),
        approved_for_training=bool(payload.get("approved_for_training", False)),
        source_interaction_id=_normalize_text(payload.get("source_interaction_id")),
        selected_model=_normalize_text(learning.get("selected_model")),
        selected_agent=_normalize_text(learning.get("selected_agent")),
        intent=_normalize_text(learning.get("intent")),
        success=bool(learning.get("success", result.get("success", True))),
        files_touched=[str(item) for item in learning.get("files_touched", []) if str(item).strip()],
        tests_run=[str(item) for item in learning.get("tests_run", []) if str(item).strip()],
        metadata=metadata,
    )


def _use_for_training(candidate: PreparedCandidate, min_quality: float, require_approved: bool) -> bool:
    if require_approved and not candidate.approved_for_training:
        return False
    return candidate.quality_score >= min_quality and candidate.success


def _split_bucket(candidate_id: str, eval_ratio: float) -> str:
    if eval_ratio <= 0:
        return "instruction"
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return "eval" if value < eval_ratio else "instruction"


def _instruction_record(candidate: PreparedCandidate) -> dict[str, Any]:
    system_text = (
        "You are OMNIRA Reasoning, a local-first planning and self-development model. "
        "Reason carefully, stay approval-aware, and produce concrete actionable outputs."
    )
    metadata = dict(candidate.metadata)
    context_lines: list[str] = []
    if metadata.get("workflow_name"):
        context_lines.append(f"Workflow: {metadata['workflow_name']}")
    if metadata.get("risk_level"):
        context_lines.append(f"Risk: {metadata['risk_level']}")
    if metadata.get("control_requirements"):
        context_lines.append(f"Control requirements: {metadata['control_requirements']}")
    if metadata.get("owner_profile_signal"):
        context_lines.append(f"Owner profile signal: {metadata['owner_profile_signal']}")
    internet_scope = metadata.get("internet_learning_scope") if isinstance(metadata.get("internet_learning_scope"), dict) else {}
    if internet_scope:
        context_lines.append(f"Internet learning scope: {internet_scope}")
    if metadata.get("compute_hints"):
        context_lines.append(f"Compute hints: {metadata['compute_hints']}")
    context_block = ""
    if context_lines:
        context_block = "\n\nContext:\n" + "\n".join(context_lines)
    return {
        "id": candidate.candidate_id,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": f"{candidate.instruction}\n\nTask:\n{candidate.input_text}{context_block}"},
            {"role": "assistant", "content": candidate.preferred_output},
        ],
        "metadata": {
            "intent": candidate.intent,
            "selected_agent": candidate.selected_agent,
            "selected_model": candidate.selected_model,
            "quality_score": candidate.quality_score,
            "files_touched": candidate.files_touched,
            "tests_run": candidate.tests_run,
            **candidate.metadata,
        },
    }


def _preference_record(candidate: PreparedCandidate) -> dict[str, Any] | None:
    if not candidate.rejected_output:
        return None
    return {
        "id": candidate.candidate_id,
        "instruction": candidate.instruction,
        "input": candidate.input_text,
        "chosen": candidate.preferred_output,
        "rejected": candidate.rejected_output,
        "metadata": {
            "intent": candidate.intent,
            "quality_score": candidate.quality_score,
            **candidate.metadata,
        },
    }


def _eval_record(candidate: PreparedCandidate) -> dict[str, Any]:
    return {
        "id": candidate.candidate_id,
        "prompt": candidate.input_text,
        "expected": candidate.preferred_output,
        "instruction": candidate.instruction,
        "metadata": {
            "intent": candidate.intent,
            "quality_score": candidate.quality_score,
            "tests_run": candidate.tests_run,
            **candidate.metadata,
        },
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def build_datasets(
    candidates_dir: Path,
    learning_dir: Path,
    output_dir: Path,
    *,
    min_quality: float,
    eval_ratio: float,
    require_approved: bool,
) -> dict[str, int]:
    learning_by_id = _learning_index(learning_dir)
    prepared: list[PreparedCandidate] = []

    for path in _iter_json_files(candidates_dir):
        payload = read_json_file(path)
        source_id = _normalize_text(payload.get("source_interaction_id"))
        candidate = _build_candidate(payload, learning_by_id.get(source_id))
        if candidate and _use_for_training(candidate, min_quality, require_approved):
            prepared.append(candidate)

    instruction_records: list[dict[str, Any]] = []
    preference_records: list[dict[str, Any]] = []
    eval_records: list[dict[str, Any]] = []

    for candidate in prepared:
        bucket = _split_bucket(candidate.candidate_id or candidate.source_interaction_id, eval_ratio)
        if bucket == "eval":
            eval_records.append(_eval_record(candidate))
        else:
            instruction_records.append(_instruction_record(candidate))
        preference_record = _preference_record(candidate)
        if preference_record is not None:
            preference_records.append(preference_record)

    _write_jsonl(output_dir / "instruction" / "reasoning.jsonl", instruction_records)
    _write_jsonl(output_dir / "preference" / "reasoning.jsonl", preference_records)
    _write_jsonl(output_dir / "eval" / "reasoning.jsonl", eval_records)

    manifest = {
        "source_candidates_dir": str(candidates_dir),
        "source_learning_dir": str(learning_dir),
        "instruction_examples": len(instruction_records),
        "preference_examples": len(preference_records),
        "eval_examples": len(eval_records),
        "min_quality": min_quality,
        "eval_ratio": eval_ratio,
        "require_approved": require_approved,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    return {
        "prepared": len(prepared),
        "instruction": len(instruction_records),
        "preference": len(preference_records),
        "eval": len(eval_records),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare OMNIRA reasoning datasets from Jarvis training candidates.")
    parser.add_argument("--candidates-dir", type=Path, default=DEFAULT_CANDIDATES_DIR)
    parser.add_argument("--learning-dir", type=Path, default=DEFAULT_LEARNING_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DATASETS_DIR)
    parser.add_argument("--min-quality", type=float, default=0.65)
    parser.add_argument("--eval-ratio", type=float, default=0.15)
    parser.add_argument("--require-approved", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = build_datasets(
        args.candidates_dir,
        args.learning_dir,
        args.output_dir,
        min_quality=args.min_quality,
        eval_ratio=args.eval_ratio,
        require_approved=args.require_approved,
    )
    print(json.dumps(counts, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .config import data_dir
from .contracts import LearningRecord, TrainingCandidate
from .secure_storage import write_json_file


LEARNING_DIR = data_dir() / "learning"
TRAINING_CANDIDATES_DIR = data_dir() / "training_candidates"


def write_learning_record(record: LearningRecord) -> Path:
    LEARNING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LEARNING_DIR / f"{record.timestamp.replace(':', '-').replace('+00:00', 'Z')}_{record.record_id}.json"
    return write_json_file(out_path, asdict(record))


def write_training_candidate(candidate: TrainingCandidate) -> Path:
    TRAINING_CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRAINING_CANDIDATES_DIR / f"{candidate.candidate_id}.json"
    return write_json_file(out_path, asdict(candidate))
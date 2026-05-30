from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .config import data_dir


INTERVIEW_DIR = data_dir() / "interviews"


@dataclass(frozen=True)
class InterviewTurn:
    role: str
    text: str
    question_type: str | None = None


@dataclass(frozen=True)
class InterviewSession:
    id: str
    created_at: str
    title: str
    turns: list[InterviewTurn] = field(default_factory=list)


def _session_path(session_id: str) -> Path:
    return INTERVIEW_DIR / f"{session_id}.json"


def _classify_question(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["tell me about a time", "example", "conflict", "challenge"]):
        return "behavioral"
    if any(word in lowered for word in ["design", "architecture", "scale", "system"]):
        return "system-design"
    if any(word in lowered for word in ["algorithm", "complexity", "code", "python", "java", "sql"]):
        return "technical"
    if any(word in lowered for word in ["resume", "background", "experience", "project"]):
        return "resume-based"
    return "general"


def create_session(title: str) -> InterviewSession:
    INTERVIEW_DIR.mkdir(parents=True, exist_ok=True)
    session = InterviewSession(
        id=str(uuid4()),
        created_at=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        title=title,
        turns=[],
    )
    _session_path(session.id).write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
    return session


def load_session(session_id: str) -> InterviewSession:
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"interview session not found: {session_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    turns = [InterviewTurn(**turn) for turn in data.get("turns", [])]
    return InterviewSession(
        id=str(data["id"]),
        created_at=str(data["created_at"]),
        title=str(data["title"]),
        turns=turns,
    )


def save_session(session: InterviewSession) -> Path:
    INTERVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_path(session.id)
    path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
    return path


def add_turn(session_id: str, role: str, text: str) -> InterviewSession:
    session = load_session(session_id)
    question_type = _classify_question(text) if role == "interviewer" else None
    turns = list(session.turns)
    turns.append(InterviewTurn(role=role, text=" ".join(text.split()), question_type=question_type))
    updated = InterviewSession(
        id=session.id,
        created_at=session.created_at,
        title=session.title,
        turns=turns,
    )
    save_session(updated)
    return updated


def list_sessions(limit: int = 20) -> list[InterviewSession]:
    if not INTERVIEW_DIR.exists():
        return []
    items: list[InterviewSession] = []
    for path in sorted(INTERVIEW_DIR.glob("*.json"), reverse=True)[:limit]:
        data = json.loads(path.read_text(encoding="utf-8"))
        turns = [InterviewTurn(**turn) for turn in data.get("turns", [])]
        items.append(
            InterviewSession(
                id=str(data["id"]),
                created_at=str(data["created_at"]),
                title=str(data["title"]),
                turns=turns,
            )
        )
    return items


def session_summary(session_id: str) -> dict[str, str | int]:
    session = load_session(session_id)
    interviewer_turns = [turn for turn in session.turns if turn.role == "interviewer"]
    candidate_turns = [turn for turn in session.turns if turn.role == "candidate"]
    latest_question_type = interviewer_turns[-1].question_type if interviewer_turns else "n/a"
    return {
        "id": session.id,
        "title": session.title,
        "turn_count": len(session.turns),
        "interviewer_turns": len(interviewer_turns),
        "candidate_turns": len(candidate_turns),
        "latest_question_type": latest_question_type or "n/a",
    }


def _score_answer(text: str) -> tuple[int, list[str]]:
    lowered = text.lower()
    notes: list[str] = []
    score = 0

    word_count = len(text.split())
    if word_count >= 12:
        score += 1
    else:
        notes.append("answer is short; add more context and specifics")

    if any(word in lowered for word in ["i ", "i first", "i then", "i led", "i coordinated", "i built"]):
        score += 1
    else:
        notes.append("answer should describe your direct actions more clearly")

    if any(word in lowered for word in ["result", "impact", "outcome", "reduced", "improved", "shipped"]):
        score += 1
    else:
        notes.append("answer is missing a concrete result or impact")

    if any(word in lowered for word in ["because", "so that", "to avoid", "to improve"]):
        score += 1
    else:
        notes.append("add reasoning behind your decisions")

    return score, notes


def coaching_summary(session_id: str) -> dict[str, str | int]:
    session = load_session(session_id)
    candidate_turns = [turn for turn in session.turns if turn.role == "candidate"]
    latest_answer = candidate_turns[-1].text if candidate_turns else ""
    score, notes = _score_answer(latest_answer) if latest_answer else (0, ["no candidate answer recorded yet"])
    latest_question_type = session_summary(session_id)["latest_question_type"]
    return {
        "id": session.id,
        "title": session.title,
        "latest_question_type": latest_question_type,
        "answer_score": score,
        "max_score": 4,
        "feedback": " | ".join(notes) if notes else "strong answer structure for this stage",
    }


def coaching_drills(limit: int = 20) -> list[str]:
    weakness_counts: dict[str, int] = {}
    for session in list_sessions(limit=limit):
        feedback = str(coaching_summary(session.id)["feedback"])
        for note in [part.strip() for part in feedback.split("|") if part.strip()]:
            weakness_counts[note] = weakness_counts.get(note, 0) + 1

    drills: list[str] = []
    for note, count in sorted(weakness_counts.items(), key=lambda item: item[1], reverse=True):
        if "short" in note:
            drills.append(f"{count}x: practice 60-second answers with context, action, and result")
        elif "direct actions" in note:
            drills.append(f"{count}x: rewrite answers to emphasize what you personally did")
        elif "result or impact" in note:
            drills.append(f"{count}x: add measurable impact or outcome to each answer")
        elif "reasoning" in note:
            drills.append(f"{count}x: explain why you chose each major decision")
        else:
            drills.append(f"{count}x: review feedback theme - {note}")
    return drills
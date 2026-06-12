from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import json

from .response_envelope import JarvisResponseEnvelope


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class _Serializable:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True)


@dataclass(slots=True)
class OwnerCommand(_Serializable):
    command_id: str = field(default_factory=lambda: new_id("cmd"))
    text: str = ""
    source: str = "text"
    owner: str = "Vivek"
    timestamp: str = field(default_factory=utc_timestamp)
    context: dict[str, Any] = field(default_factory=dict)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IntentResult(_Serializable):
    intent: str = "general_conversation"
    confidence: float = 0.0
    entities: dict[str, Any] = field(default_factory=dict)
    requires_omnira: bool = False
    local_command: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionPlan(_Serializable):
    plan_id: str = field(default_factory=lambda: new_id("plan"))
    goal: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    selected_agent: str = "commander"
    agent_tasks: list["AgentTask"] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    risk_level: str = "low"
    approval_required: bool = False
    verification_steps: list[str] = field(default_factory=list)
    rollback_plan: list[str] = field(default_factory=list)
    control_requirements: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentTask(_Serializable):
    task_id: str = field(default_factory=lambda: new_id("task"))
    agent: str = "commander"
    intent: str = "general_conversation"
    input: dict[str, Any] = field(default_factory=dict)
    tools_allowed: list[str] = field(default_factory=list)
    risk_level: str = "low"
    status: str = "pending"
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolRequest(_Serializable):
    tool_name: str = ""
    action: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    approval_required: bool = False
    dry_run: bool = True
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ApprovalRequest(_Serializable):
    approval_id: str = field(default_factory=lambda: new_id("approval"))
    action_summary: str = ""
    risk_level: str = "high"
    files_affected: list[str] = field(default_factory=list)
    commands_to_run: list[str] = field(default_factory=list)
    plan_summary: str = ""
    approve_options: list[str] = field(default_factory=lambda: ["approve", "reject", "revise"])
    expires_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LearningRecord(_Serializable):
    record_id: str = field(default_factory=lambda: new_id("learn"))
    command: str = ""
    transcript: str = ""
    intent: str = ""
    selected_agent: str = ""
    selected_model: str = ""
    plan: dict[str, Any] = field(default_factory=dict)
    tools_used: list[dict[str, Any]] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    owner_feedback: str = ""
    memory_saved: bool = False
    training_candidate: bool = False
    timestamp: str = field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrainingCandidate(_Serializable):
    candidate_id: str = field(default_factory=lambda: new_id("train"))
    instruction: str = ""
    input: str = ""
    preferred_output: str = ""
    rejected_output: str = ""
    source_interaction_id: str = ""
    quality_score: float = 0.0
    reviewed: bool = False
    approved_for_training: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeStatus(_Serializable):
    jarvis_alive: bool = True
    control_mode: str = "active"
    commands_blocked: bool = False
    control_updated_at: str = ""
    control_note: str = ""
    voice_online: bool = False
    omnira_online: bool = False
    active_model: str = ""
    active_agent: str = ""
    memory_online: bool = False
    tools_ready: bool = False
    active_tasks: int = 0
    pending_approvals: int = 0
    cpu_percent: float | None = None
    ram_percent: float | None = None
    warnings: list[str] = field(default_factory=list)
    last_error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolResult(_Serializable):
    success: bool = True
    output: str = ""
    error: str = ""
    files_changed: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    diff_summary: str = ""
    verification: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ApprovalRequest",
    "AgentTask",
    "ExecutionPlan",
    "IntentResult",
    "JarvisResponseEnvelope",
    "LearningRecord",
    "OwnerCommand",
    "RuntimeStatus",
    "ToolRequest",
    "ToolResult",
    "TrainingCandidate",
    "new_id",
    "utc_timestamp",
]
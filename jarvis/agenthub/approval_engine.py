from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .approval_queue import create_pending_approval
from .contracts import ApprovalRequest, ExecutionPlan
from .protocols import APPROVAL_REQUIRED_RISKS


@dataclass(slots=True)
class ApprovalDecision:
    required: bool
    risk_level: str
    reason: str


class ApprovalEngine:
    def assess(self, plan: ExecutionPlan) -> ApprovalDecision:
        if plan.approval_required or plan.risk_level in APPROVAL_REQUIRED_RISKS:
            return ApprovalDecision(True, plan.risk_level, "risk gate triggered")
        return ApprovalDecision(False, plan.risk_level, "low-risk plan")

    def create_request(
        self,
        plan: ExecutionPlan,
        *,
        source: str = "jarvis.commander",
        stage: bool = True,
    ) -> ApprovalRequest:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
        approval_id = ""
        if stage:
            staged = create_pending_approval(
                task=plan.goal,
                risk=plan.risk_level,
                source=source,
                note="Commander requested approval before risky execution.",
            )
            approval_id = staged.id
        else:
            approval_id = f"preview-{plan.plan_id}"
        return ApprovalRequest(
            approval_id=approval_id,
            action_summary=plan.goal,
            risk_level=plan.risk_level,
            files_affected=list(plan.metadata.get("files_affected", [])),
            commands_to_run=list(plan.metadata.get("commands_to_run", [])),
            plan_summary="; ".join(str(step.get("summary") or step.get("action") or "step") for step in plan.steps),
            expires_at=expires_at,
            metadata={"plan_id": plan.plan_id, "selected_agent": plan.selected_agent},
        )
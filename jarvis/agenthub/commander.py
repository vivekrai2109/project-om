from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .approval_engine import ApprovalEngine
from .assistant_core import handle_assistant_core, should_use_fast_assistant_route
from .backend_client import OmniraClient, build_routing_profile, create_openai_client, resolve_model_name, resolve_omnira_agent_name
from .code_patch import CodePatchEngine
from .config import BASE_DIR, load_config
from .contracts import AgentTask, ApprovalRequest, ExecutionPlan, IntentResult, LearningRecord, OwnerCommand, ToolRequest, TrainingCandidate
from .events import LocalEventBus
from .interaction_log import InteractionRecord, write_interaction_record
from .learning import write_learning_record, write_training_candidate
from .memory_control import (
    apply_internet_learning_domain_update,
    load_memory_control_state,
    parse_memory_control_details,
    parse_memory_control_action,
    set_memory_control_state,
    should_create_training_candidate,
    should_skip_learning_capture,
    summarize_memory_control,
)
from .memory import append_memory, load_memory, project_id
from .secure_storage import iter_json_like_files
from .protocols import (
    APPROVAL_REQUIRED_RISKS,
    APPROVAL_RESPONSE_PATTERNS,
    CODE_CHANGE_PATTERNS,
    DEBUGGING_PATTERNS,
    INTENT_AGENT_MAP,
    LOCAL_COMMAND_PATTERNS,
    MEMORY_RECALL_PATTERNS,
    MEMORY_SAVE_PATTERNS,
    OWNER_NAME,
    REPO_ANALYSIS_PATTERNS,
    RESEARCH_PATTERNS,
    RISK_BY_INTENT,
    SELF_CODE_CHANGE_PATTERNS,
    SELF_CODE_WORKFLOW_STEPS,
    SELF_UI_PATTERNS,
    SELF_UI_WORKFLOW_STEPS,
    UI_PROTOCOL_RULES,
)
from .repo_intelligence import RepoIntelligence
from .response_envelope import JarvisResponseEnvelope, build_response_envelope
from .runtime import JarvisRuntime
from .runtime_actions import maybe_execute_runtime_action
from .tool_runtime import SafeToolRuntime


class JarvisCommander:
    def __init__(
        self,
        *,
        project_path: str | None = None,
        event_bus: LocalEventBus | None = None,
        runtime: JarvisRuntime | None = None,
        profile: str = "personal",
        stage_approvals: bool = True,
    ) -> None:
        self._project_path = str(Path(project_path or BASE_DIR))
        self._config = load_config()
        self._event_bus = event_bus or LocalEventBus()
        self._runtime = runtime or JarvisRuntime(project_path=self._project_path, event_bus=self._event_bus)
        self._approval_engine = ApprovalEngine()
        self._profile = profile
        self._stage_approvals = stage_approvals
        self._project_id = project_id(self._project_path)
        self._repo_intelligence = RepoIntelligence(self._project_path)
        self._tool_runtime = SafeToolRuntime(project_path=self._project_path, profile=profile)
        self._code_patch_engine = CodePatchEngine(self._project_path)
        self._runtime.start()

    def handle_owner_command(self, command: OwnerCommand) -> JarvisResponseEnvelope:
        self._runtime.begin_task(command.command_id)
        self._event_bus.publish("intent.detected", {"text": command.text}, correlation_id=command.command_id, task_id=command.command_id)
        try:
            intent = self.classify_intent(command.text, command.context)
            allowed, reason = self._runtime.can_accept_command(command.text, intent.intent)
            if not allowed:
                self._runtime.finish_task(command.command_id, success=True)
                status = self._runtime.status()
                return self.build_response_envelope(
                    reply_text=reason,
                    speech_text=f"Jarvis is {status.control_mode}.",
                    state="warning",
                    intent=intent.intent,
                    agent="commander",
                    model=self._config.model,
                    provider="local-runtime",
                    confidence=intent.confidence,
                    decision_path=["understand", "control_gate"],
                    workflow_trace=[{"step": "control_gate", "status": "blocked", "detail": reason}],
                    safety_flags=["runtime_control_block"],
                    approval_required=False,
                    risk_level="low",
                    metadata={"control_mode": status.control_mode},
                )
            self._event_bus.publish("agent.selected", {"intent": intent.intent, "agent": self.select_agent(intent, command.context)}, correlation_id=command.command_id, task_id=command.command_id)
            plan = self.create_plan(intent, command, command.context)
            self._event_bus.publish("plan.created", {"plan_id": plan.plan_id, "intent": intent.intent}, correlation_id=command.command_id, task_id=command.command_id)
            risk_level = self.assess_risk(plan)
            plan.risk_level = risk_level
            plan.approval_required = risk_level in APPROVAL_REQUIRED_RISKS or plan.approval_required
            self._event_bus.publish("risk.assessed", {"plan_id": plan.plan_id, "risk_level": risk_level}, correlation_id=command.command_id, task_id=command.command_id)
            approval_request = self.require_approval_if_needed(plan)
            if approval_request is not None:
                self._event_bus.publish("approval.required", approval_request.to_dict(), correlation_id=command.command_id, task_id=command.command_id)
                response = self.build_response_envelope(
                    reply_text=(
                        "I can prepare this change, but it crosses the supervised boundary. "
                        f"Approval is required before execution. Approval id: {approval_request.approval_id}."
                    ),
                    speech_text="Approval is required before I proceed.",
                    state="approval_required",
                    intent=intent.intent,
                    agent=plan.selected_agent,
                    model=plan.metadata.get("resolved_model", self._config.model),
                    provider=plan.metadata.get("provider", self._config.backend),
                    confidence=intent.confidence,
                    decision_path=["understand", "plan", "risk_check", "approval_gate"],
                    workflow_trace=[
                        {"step": "plan", "status": "ok", "detail": plan.goal},
                        {"step": "risk_check", "status": "warning", "detail": risk_level},
                        {"step": "approval", "status": "pending", "detail": approval_request.approval_id},
                    ],
                    safety_flags=["owner_approval_required"],
                    approval_required=True,
                    risk_level=risk_level,
                        metadata={
                            "plan": plan.to_dict(),
                            "approval_request": approval_request.to_dict(),
                            "model_rationale": self._build_model_rationale(plan, intent),
                        },
                )
                self.capture_learning(command, intent, plan, {"success": True, "approval_request": approval_request.to_dict()}, response)
                self._runtime.finish_task(command.command_id, success=True)
                return response

            result = self.execute_plan(plan)
            verification = self.verify_result(result, plan)
            response = self.build_response_envelope(
                reply_text=str(result.get("reply_text") or result.get("output") or ""),
                speech_text=str(result.get("speech_text") or result.get("reply_text") or result.get("output") or ""),
                state=str(result.get("state") or ("speaking" if result.get("success") else "error")),
                intent=intent.intent,
                agent=str(result.get("agent") or plan.selected_agent),
                model=str(result.get("model") or plan.metadata.get("resolved_model") or self._config.model),
                provider=str(result.get("provider") or self._config.backend),
                confidence=intent.confidence,
                decision_path=["understand", "plan", "risk_check", "act", "verify", "respond", "learn"],
                workflow_trace=list(result.get("workflow_trace") or []) + [
                    {"step": "verify", "status": "ok" if verification.get("ok") else "warning", "detail": verification.get("detail", "")}
                ],
                memory_hits=list(result.get("memory_hits") or []),
                tool_calls=list(result.get("tool_calls") or []),
                visualization=dict(result.get("visualization") or {}),
                safety_flags=list(result.get("safety_flags") or []),
                approval_required=False,
                risk_level=plan.risk_level,
                error=result.get("error"),
                metadata={
                    "plan": plan.to_dict(),
                    "verification": verification,
                    "model_rationale": self._build_model_rationale(plan, intent, result=result),
                    **dict(result.get("metadata") or {}),
                },
            )
            self.capture_learning(command, intent, plan, result, response)
            self._runtime.finish_task(command.command_id, success=bool(result.get("success", True)), error=str(result.get("error") or ""))
            return response
        except Exception as exc:
            self._runtime.finish_task(command.command_id, success=False, error=str(exc))
            self._event_bus.publish("error.raised", {"error": str(exc)}, correlation_id=command.command_id, task_id=command.command_id)
            response = self.build_response_envelope(
                reply_text=f"Commander failed: {exc}",
                speech_text="I hit an internal error while processing that request.",
                state="error",
                intent="debugging",
                agent="commander",
                model=self._config.model,
                provider=self._config.backend,
                confidence=0.0,
                decision_path=["understand", "error"],
                workflow_trace=[{"step": "error", "status": "failed", "detail": str(exc)}],
                safety_flags=["execution_error"],
                approval_required=False,
                risk_level="medium",
                error={"message": str(exc)},
            )
            return response

    def classify_intent(self, command_text: str, context: dict[str, Any] | None = None) -> IntentResult:
        text = " ".join(str(command_text or "").split())
        lowered = text.lower()
        if not lowered:
            return IntentResult(intent="general_conversation", confidence=0.0)

        for intent_name, pattern in LOCAL_COMMAND_PATTERNS:
            if pattern.search(text):
                return IntentResult(intent=intent_name, confidence=0.95, local_command=text, metadata={"path": "local"})
        if any(pattern.search(text) for pattern in MEMORY_SAVE_PATTERNS):
            return IntentResult(intent="memory_save", confidence=0.92, metadata={"path": "learning"})
        if any(pattern.search(text) for pattern in MEMORY_RECALL_PATTERNS):
            return IntentResult(intent="memory_recall", confidence=0.84, metadata={"path": "memory"})
        if any(pattern.search(text) for pattern in APPROVAL_RESPONSE_PATTERNS):
            return IntentResult(intent="approval_response", confidence=0.80, metadata={"path": "approval"})
        if any(pattern.search(text) for pattern in SELF_UI_PATTERNS):
            return IntentResult(intent="self_improve_ui", confidence=0.91, requires_omnira=False, metadata={"path": "proposal"})
        if any(pattern.search(text) for pattern in SELF_CODE_CHANGE_PATTERNS):
            return IntentResult(intent="self_code_change", confidence=0.93, requires_omnira=False, metadata={"path": "proposal"})
        if any(pattern.search(text) for pattern in CODE_CHANGE_PATTERNS):
            return IntentResult(intent="code_change", confidence=0.88, requires_omnira=False, metadata={"path": "proposal"})
        if any(pattern.search(text) for pattern in REPO_ANALYSIS_PATTERNS):
            return IntentResult(intent="repo_analysis", confidence=0.84, requires_omnira=False, metadata={"path": "analysis"})
        if any(pattern.search(text) for pattern in DEBUGGING_PATTERNS):
            return IntentResult(intent="debugging", confidence=0.78, requires_omnira=True, metadata={"path": "omnira"})
        if any(pattern.search(text) for pattern in RESEARCH_PATTERNS):
            return IntentResult(intent="research", confidence=0.82, requires_omnira=True, metadata={"path": "omnira"})
        if should_use_fast_assistant_route(text):
            return IntentResult(intent="general_conversation", confidence=0.76, requires_omnira=False, metadata={"path": "fast_assistant"})
        return IntentResult(intent="general_conversation", confidence=0.62, requires_omnira=True, metadata={"path": "omnira"})

    def create_plan(self, intent: IntentResult, command: OwnerCommand, context: dict[str, Any] | None = None) -> ExecutionPlan:
        selected_agent = self.select_agent(intent, context)
        required_tools: list[str] = []
        expected_outputs = ["structured_response_envelope"]
        verification_steps = ["verify_result"]
        rollback_plan = ["no destructive action has been executed"]
        metadata: dict[str, Any] = {
            "command_id": command.command_id,
            "source": command.source,
            "owner": command.owner or OWNER_NAME,
            "intent": intent.intent,
        }

        if intent.local_command and intent.intent not in {"memory_control", "privacy_status"}:
            required_tools.append("runtime_action")
            expected_outputs.append("runtime_action_result")
        elif intent.intent in {"general_conversation", "research", "debugging"} and intent.requires_omnira:
            required_tools.append("omnira.chat")
            expected_outputs.append("omnira_response")
            metadata["provider"] = self._config.backend
        elif intent.intent == "repo_analysis":
            required_tools.extend(["inspect_repo", "search_code"])
            expected_outputs.append("repo_summary")
            verification_steps.append("local_repo_scan")
            metadata["proposal_only"] = False
            metadata["workflow_name"] = "repo_analysis"
        elif intent.intent == "self_code_change":
            required_tools.extend(["inspect_repo", "write_file_proposal"])
            expected_outputs.append("self_code_change_dry_run")
            verification_steps.extend(["proposal_validation", "manual_review", "compile_check"])
            metadata["proposal_only"] = True
            metadata["apply_requires_approval"] = True
            metadata["workflow_name"] = "self_code_change"
            metadata["workflow_steps"] = list(SELF_CODE_WORKFLOW_STEPS)
        elif intent.intent == "self_improve_ui":
            required_tools.extend(["inspect_repo", "write_file_proposal"])
            expected_outputs.append("self_improve_ui_dry_run")
            verification_steps.extend(["proposal_validation", "manual_review", "compile_check", "start_app_check"])
            metadata["proposal_only"] = True
            metadata["apply_requires_approval"] = True
            metadata["workflow_name"] = "self_improve_ui"
            metadata["workflow_steps"] = list(SELF_UI_WORKFLOW_STEPS)
            metadata["ui_protocol_rules"] = list(UI_PROTOCOL_RULES)
        elif intent.intent in {"code_change", "self_code_change", "self_improve_ui"}:
            required_tools.extend(["inspect_repo", "write_file_proposal"])
            expected_outputs.append("patch_proposal")
            verification_steps.extend(["proposal_validation", "manual_review"])
            metadata["proposal_only"] = True
            metadata["apply_requires_approval"] = True
            metadata["workflow_name"] = "code_change"
        elif intent.intent in {"memory_save", "memory_recall"}:
            required_tools.append("memory")
        elif intent.intent in {"memory_control", "privacy_status"}:
            required_tools.append("memory")

        routing_profile = build_routing_profile(selected_agent, None, self._config, dynamic_routing=intent.requires_omnira)
        plan = ExecutionPlan(
            goal=command.text,
            steps=self._plan_steps(intent, command.text),
            selected_agent=selected_agent,
            agent_tasks=self._build_agent_tasks(intent, command.text, selected_agent),
            required_tools=required_tools,
            expected_outputs=expected_outputs,
            risk_level=RISK_BY_INTENT.get(intent.intent, "medium"),
            approval_required=RISK_BY_INTENT.get(intent.intent, "medium") in APPROVAL_REQUIRED_RISKS,
            verification_steps=verification_steps,
            rollback_plan=rollback_plan,
            control_requirements=self._control_requirements_for_intent(intent.intent),
            metadata=metadata,
        )
        plan.metadata["resolved_model"] = routing_profile.model_name
        plan.metadata["compute_mode"] = routing_profile.compute_mode
        plan.metadata["max_output_tokens"] = routing_profile.max_output_tokens
        plan.metadata["reasoning_effort"] = routing_profile.reasoning_effort
        plan.metadata["pinned_model"] = str(load_memory_control_state().pinned_model or "").strip()
        return plan

    def _build_model_rationale(
        self,
        plan: ExecutionPlan,
        intent: IntentResult,
        *,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_model = str((result or {}).get("model") or plan.metadata.get("resolved_model") or self._config.model or "dynamic").strip()
        compute_mode = str(plan.metadata.get("compute_mode") or "balanced").strip() or "balanced"
        reasoning_effort = str(plan.metadata.get("reasoning_effort") or self._config.reasoning_effort).strip()
        max_output_tokens = int(plan.metadata.get("max_output_tokens") or self._config.max_output_tokens)
        pinned_model = str(plan.metadata.get("pinned_model") or "").strip()
        intent_path = str(intent.metadata.get("path") or "standard").strip() or "standard"
        provider = str((result or {}).get("provider") or plan.metadata.get("provider") or self._config.backend).strip()
        selected_agent = str((result or {}).get("agent") or plan.selected_agent or "commander").strip()
        dynamic_routing = bool(intent.requires_omnira)

        if pinned_model:
            reason = f"Pinned model override is active, so Jarvis stayed on {resolved_model}."
        elif dynamic_routing:
            reason = f"Intent path '{intent_path}' can use OMNIRA routing, so Jarvis selected {resolved_model} for the {selected_agent} lane."
        elif intent_path == "fast_assistant":
            reason = f"This turn stayed on the fast assistant path, so Jarvis used {resolved_model} for lower latency."
        elif intent_path == "proposal":
            reason = f"This turn prepared a supervised proposal, so Jarvis stayed on the {selected_agent} lane with {resolved_model}."
        else:
            reason = f"Jarvis selected {resolved_model} for the {selected_agent} lane under {compute_mode} mode."

        return {
            "summary": reason,
            "selected_agent": selected_agent,
            "selected_model": resolved_model,
            "provider": provider,
            "compute_mode": compute_mode,
            "reasoning_effort": reasoning_effort,
            "max_output_tokens": max_output_tokens,
            "pinned_model": pinned_model,
            "intent_path": intent_path,
            "dynamic_routing": dynamic_routing,
        }

    def select_agent(self, intent: IntentResult, context: dict[str, Any] | None = None) -> str:
        return INTENT_AGENT_MAP.get(intent.intent, "commander")

    def assess_risk(self, plan: ExecutionPlan) -> str:
        risk = str(plan.risk_level or "medium").lower()
        goal = plan.goal.lower()
        intent_name = str(plan.metadata.get("intent") or "")
        if intent_name in {"voice_control", "open_operations", "hide_operations", "backend_status", "resource_status", "model_status", "memory_save", "memory_recall", "memory_control", "privacy_status", "learning_readiness"}:
            return risk
        if any(token in goal for token in ("delete", "remove", "deploy", "credential", "secret", "production")):
            return "critical"
        if any(token in goal for token in ("apply", "patch", "write", "rewrite", "modify", "commit")):
            return "high" if risk == "medium" else risk
        return risk

    def require_approval_if_needed(self, plan: ExecutionPlan) -> ApprovalRequest | None:
        if bool(plan.metadata.get("proposal_only")):
            return None
        decision = self._approval_engine.assess(plan)
        if not decision.required:
            return None
        return self._approval_engine.create_request(plan, stage=self._stage_approvals)

    def execute_plan(self, plan: ExecutionPlan) -> dict[str, Any]:
        intent = str(plan.metadata.get("intent") or "")
        command_text = plan.goal
        control_action = self._runtime.control_action_for_text(command_text)
        if control_action is not None:
            if control_action == "status":
                status = self._runtime.status()
                return {
                    "success": True,
                    "reply_text": f"Jarvis control mode is {status.control_mode}. Active tasks: {status.active_tasks}. Pending approvals: {status.pending_approvals}.",
                    "speech_text": f"Jarvis is {status.control_mode}.",
                    "state": "speaking",
                    "agent": "commander",
                    "provider": "local-runtime",
                    "workflow_trace": [{"step": "control.status", "status": "ok", "detail": status.control_mode}],
                    "metadata": {"runtime_status": status.to_dict()},
                }
            status = self._runtime.set_control_mode(control_action, source="owner_command", note=command_text)
            return {
                "success": True,
                "reply_text": f"Jarvis control mode set to {status.control_mode}.",
                "speech_text": f"Jarvis is now {status.control_mode}.",
                "state": "speaking",
                "agent": "commander",
                "provider": "local-runtime",
                "workflow_trace": [{"step": "control.set", "status": "ok", "detail": status.control_mode}],
                "metadata": {"runtime_status": status.to_dict()},
            }
        if plan.required_tools == ["runtime_action"] and intent not in {"backend_status", "resource_status", "model_status", "learning_readiness"}:
            result = maybe_execute_runtime_action(
                command_text,
                self._project_path,
                profile=self._profile,
                approve_runtime=False,
                source="jarvis.commander",
                note="Commander local action",
            )
            return {
                "success": result.handled,
                "reply_text": result.message or "Local command processed.",
                "speech_text": result.message or "Local command processed.",
                "state": "speaking" if result.handled else "idle",
                "agent": "commander",
                "provider": "local-runtime",
                "tool_calls": [{"name": result.action or "runtime_action", "status": "completed" if result.handled else "ignored"}],
                "workflow_trace": [{"step": "runtime_action", "status": "ok" if result.handled else "skipped", "detail": result.message}],
                "metadata": {"local_command": True},
            }

        if intent == "backend_status" or "backend status" in command_text.lower():
            status = self._runtime.refresh_status(active_agent=plan.selected_agent, active_model=str(plan.metadata.get("resolved_model") or self._config.model))
            return {
                "success": True,
                "reply_text": f"Jarvis is online. OMNIRA is {'online' if status.omnira_online else 'offline'}. Active model: {status.active_model or 'unknown'}. Pending approvals: {status.pending_approvals}.",
                "speech_text": f"OMNIRA is {'online' if status.omnira_online else 'offline'}.",
                "state": "speaking",
                "agent": "omnira_bridge",
                "provider": "local-runtime",
                "workflow_trace": [{"step": "runtime.status", "status": "ok", "detail": "backend health checked"}],
                "metadata": {"runtime_status": status.to_dict()},
            }

        if intent == "model_status" or "model status" in command_text.lower() or "routing status" in command_text.lower():
            memory_control = load_memory_control_state()
            routing_profile = build_routing_profile(
                plan.selected_agent,
                None,
                self._config,
                dynamic_routing=False,
                compute_mode=memory_control.compute_mode,
            )
            status = self._runtime.refresh_status(
                active_agent=plan.selected_agent,
                active_model=str(routing_profile.model_name or self._config.model),
            )
            return {
                "success": True,
                "reply_text": (
                    f"Compute mode: {routing_profile.compute_mode}. "
                    f"Resolved model: {routing_profile.model_name or 'dynamic'}. "
                    f"Reasoning effort: {routing_profile.reasoning_effort}. "
                    f"Max output tokens: {routing_profile.max_output_tokens}. "
                    f"Backend: {'online' if status.omnira_online else 'offline'}."
                ),
                "speech_text": "Routing status is ready.",
                "state": "speaking",
                "agent": "omnira_bridge",
                "provider": "local-runtime",
                "workflow_trace": [{"step": "runtime.model_status", "status": "ok", "detail": routing_profile.compute_mode}],
                "metadata": {
                    "runtime_status": status.to_dict(),
                    "routing_profile": {
                        "compute_mode": routing_profile.compute_mode,
                        "model_name": routing_profile.model_name,
                        "reasoning_effort": routing_profile.reasoning_effort,
                        "max_output_tokens": routing_profile.max_output_tokens,
                    },
                },
            }

        if intent == "resource_status" or "resource status" in command_text.lower() or "system status" in command_text.lower():
            status = self._runtime.heartbeat()
            return {
                "success": True,
                "reply_text": f"CPU: {status.cpu_percent if status.cpu_percent is not None else 'n/a'} percent. RAM: {status.ram_percent if status.ram_percent is not None else 'n/a'} percent. Active tasks: {status.active_tasks}.",
                "speech_text": "Resource status is ready.",
                "state": "speaking",
                "agent": "resource_manager",
                "provider": "local-runtime",
                "workflow_trace": [{"step": "runtime.heartbeat", "status": "ok", "detail": "resource snapshot refreshed"}],
                "metadata": {"runtime_status": status.to_dict()},
            }

        if intent == "memory_save":
            memory_control = load_memory_control_state()
            if not memory_control.memory_enabled:
                return {
                    "success": True,
                    "reply_text": "Memory capture is currently off. Turn memory back on if you want me to store new preferences.",
                    "speech_text": "Memory capture is off.",
                    "state": "warning",
                    "agent": "memory",
                    "provider": "local-memory",
                    "workflow_trace": [{"step": "memory.save", "status": "blocked", "detail": "memory disabled by owner"}],
                    "metadata": {"memory_saved": False, "memory_control": memory_control.to_dict()},
                }
            payload = self._extract_memory_payload(command_text)
            append_memory(self._project_id, payload)
            return {
                "success": True,
                "reply_text": f"Saved to memory: {payload}",
                "speech_text": "I saved that preference.",
                "state": "speaking",
                "agent": "memory",
                "provider": "local-memory",
                "memory_hits": [payload],
                "workflow_trace": [{"step": "memory.save", "status": "ok", "detail": payload}],
                "metadata": {"memory_saved": True, "memory_control": memory_control.to_dict()},
            }

        if intent == "memory_recall":
            memory_text = load_memory(self._project_id).strip()
            excerpt = memory_text[-400:] if memory_text else "No stored memory yet."
            return {
                "success": True,
                "reply_text": excerpt,
                "speech_text": "I checked local memory.",
                "state": "speaking",
                "agent": "memory",
                "provider": "local-memory",
                "memory_hits": [excerpt] if memory_text else [],
                "workflow_trace": [{"step": "memory.recall", "status": "ok", "detail": "local memory loaded"}],
            }

        if intent == "privacy_status":
            state = load_memory_control_state()
            summary, payload = summarize_memory_control(state)
            return {
                "success": True,
                "reply_text": summary,
                "speech_text": "Privacy and learning status is ready.",
                "state": "speaking",
                "agent": "memory",
                "provider": "local-memory",
                "workflow_trace": [{"step": "memory.control.status", "status": "ok", "detail": state.note or "local-first controls loaded"}],
                "metadata": {"memory_control": payload},
            }

        if intent == "learning_readiness":
            return self._learning_readiness_status()

        if intent == "memory_control":
            action = parse_memory_control_action(command_text)
            details = parse_memory_control_details(command_text)
            if action == "exclude_current_turn":
                state = load_memory_control_state()
                return {
                    "success": True,
                    "reply_text": "I will not remember or train on this turn.",
                    "speech_text": "I will not remember this turn.",
                    "state": "speaking",
                    "agent": "memory",
                    "provider": "local-memory",
                    "workflow_trace": [{"step": "memory.control.exclude_turn", "status": "ok", "detail": "current turn excluded from learning capture"}],
                    "metadata": {"skip_learning_capture": True, "memory_control": state.to_dict()},
                }
            if action == "compute_mode":
                state = set_memory_control_state(
                    compute_mode=str(details.get("compute_mode") or "balanced"),
                    updated_by="owner_command",
                    note=command_text,
                )
                summary, payload = summarize_memory_control(state)
                return {
                    "success": True,
                    "reply_text": summary,
                    "speech_text": "I updated your compute mode.",
                    "state": "speaking",
                    "agent": "memory",
                    "provider": "local-memory",
                    "workflow_trace": [{"step": "memory.control.compute_mode", "status": "ok", "detail": str(details.get("compute_mode") or state.compute_mode)}],
                    "metadata": {"memory_control": payload},
                }
            if action == "internet_domains":
                current_state = load_memory_control_state()
                domains = apply_internet_learning_domain_update(
                    current_state,
                    str(details.get("domain_operation") or "set"),
                    list(details.get("domains") or []),
                )
                state = set_memory_control_state(
                    internet_learning_domains=domains,
                    updated_by="owner_command",
                    note=command_text,
                )
                summary, payload = summarize_memory_control(state)
                return {
                    "success": True,
                    "reply_text": summary,
                    "speech_text": "I updated your internet learning domains.",
                    "state": "speaking",
                    "agent": "memory",
                    "provider": "local-memory",
                    "workflow_trace": [{"step": "memory.control.internet_domains", "status": "ok", "detail": str(details.get("domain_operation") or "set")}],
                    "metadata": {"memory_control": payload},
                }
            if action == "pin_model":
                state = set_memory_control_state(
                    pinned_model=str(details.get("pinned_model") or "").strip(),
                    updated_by="owner_command",
                    note=command_text,
                )
                summary, payload = summarize_memory_control(state)
                return {
                    "success": True,
                    "reply_text": summary,
                    "speech_text": "I pinned your active model preference.",
                    "state": "speaking",
                    "agent": "memory",
                    "provider": "local-memory",
                    "workflow_trace": [{"step": "memory.control.pin_model", "status": "ok", "detail": str(details.get("pinned_model") or state.pinned_model)}],
                    "metadata": {"memory_control": payload},
                }
            state = {
                "memory_off": lambda: set_memory_control_state(memory_enabled=False, updated_by="owner_command", note=command_text),
                "memory_on": lambda: set_memory_control_state(memory_enabled=True, updated_by="owner_command", note=command_text),
                "training_off": lambda: set_memory_control_state(training_enabled=False, updated_by="owner_command", note=command_text),
                "training_on": lambda: set_memory_control_state(training_enabled=True, updated_by="owner_command", note=command_text),
                "observation_off": lambda: set_memory_control_state(observation_enabled=False, updated_by="owner_command", note=command_text),
                "observation_on": lambda: set_memory_control_state(observation_enabled=True, updated_by="owner_command", note=command_text),
                "profile_off": lambda: set_memory_control_state(profile_learning_enabled=False, updated_by="owner_command", note=command_text),
                "profile_on": lambda: set_memory_control_state(profile_learning_enabled=True, updated_by="owner_command", note=command_text),
                "internet_off": lambda: set_memory_control_state(internet_learning_enabled=False, updated_by="owner_command", note=command_text),
                "internet_on": lambda: set_memory_control_state(internet_learning_enabled=True, updated_by="owner_command", note=command_text),
                "unpin_model": lambda: set_memory_control_state(pinned_model="", updated_by="owner_command", note=command_text),
            }.get(action or "", lambda: load_memory_control_state())()
            summary, payload = summarize_memory_control(state)
            return {
                "success": True,
                "reply_text": summary,
                "speech_text": "I updated your privacy controls.",
                "state": "speaking",
                "agent": "memory",
                "provider": "local-memory",
                "workflow_trace": [{"step": "memory.control.update", "status": "ok", "detail": action or "no_change"}],
                "metadata": {"memory_control": payload},
            }

        if intent == "repo_analysis":
            return self._run_repo_analysis(plan)

        if intent == "self_code_change":
            return self._run_self_code_change_workflow(plan)

        if intent == "self_improve_ui":
            return self._run_self_improve_ui_workflow(plan)

        if intent == "code_change":
            return self._dry_run_proposal(plan)

        if intent == "approval_response":
            return {
                "success": True,
                "reply_text": "Approval responses are recognized, but final approval execution stays on the existing approval queue and supervised runtime path.",
                "speech_text": "I recognized that as an approval response.",
                "state": "speaking",
                "agent": "security",
                "provider": "local-runtime",
                "workflow_trace": [{"step": "approval.response", "status": "ok", "detail": "recognized approval intent"}],
                "metadata": {"placeholder": True},
            }

        assistant_result = handle_assistant_core(
            command_text,
            project_path=self._project_path,
            backend_status=f"OMNIRA is {'online' if self._runtime.status().omnira_online else 'offline'}.",
            backend_detail=str(self._runtime.status().metadata.get("omnira_detail", "")),
            active_model=self._runtime.status().active_model,
        )
        if assistant_result.handled:
            return {
                "success": True,
                "reply_text": assistant_result.message,
                "speech_text": assistant_result.message,
                "state": assistant_result.mood,
                "agent": "commander",
                "provider": "assistant_core",
                "workflow_trace": [{"step": "assistant_core", "status": "ok", "detail": assistant_result.intent}],
            }

        return self._call_omnira(plan)

    def verify_result(self, result: dict[str, Any], plan: ExecutionPlan) -> dict[str, Any]:
        if result.get("success"):
            return {"ok": True, "detail": "result completed"}
        return {"ok": False, "detail": str(result.get("error") or "execution failed")}

    def capture_learning(
        self,
        command: OwnerCommand,
        intent: IntentResult,
        plan: ExecutionPlan,
        result: dict[str, Any],
        response: JarvisResponseEnvelope,
    ) -> None:
        memory_control = load_memory_control_state()
        if bool(result.get("metadata", {}).get("skip_learning_capture", False)) or should_skip_learning_capture(command.text, memory_control):
            self._event_bus.publish(
                "learning.skipped",
                {"command_id": command.command_id, "reason": "memory_control", "observation_enabled": memory_control.observation_enabled},
                correlation_id=command.command_id,
                task_id=command.command_id,
            )
            return
        learning_record = LearningRecord(
            command=command.text,
            transcript=command.text,
            intent=intent.intent,
            selected_agent=plan.selected_agent,
            selected_model=str(response.model or ""),
            plan=plan.to_dict(),
            tools_used=list(response.tool_calls),
            files_touched=list(plan.metadata.get("files_affected", [])),
            tests_run=list(result.get("verification", [])),
            result={"success": result.get("success", True), "reply_text": response.reply_text, **dict(result.get("metadata") or {})},
            success=bool(result.get("success", True)),
            memory_saved=bool(result.get("metadata", {}).get("memory_saved", False)),
            training_candidate=should_create_training_candidate(intent.intent, command.text, memory_control),
            metadata={
                "command_id": command.command_id,
                "source": command.source,
                "memory_control": memory_control.to_dict(),
                "workflow_name": str(plan.metadata.get("workflow_name") or intent.intent),
                "risk_level": plan.risk_level,
                "approval_required": response.approval_required,
                "verification": self._normalize_verification_metadata(response.metadata.get("verification")),
                "control_requirements": dict(plan.control_requirements),
                "runtime_status": self._runtime.status().to_dict(),
                "compute_hints": self._normalize_mapping(self._runtime.status().metadata.get("routing_hints")),
                "owner_profile_signal": self._owner_profile_signal(intent, command, memory_control),
                "internet_learning_scope": {
                    "enabled": memory_control.internet_learning_enabled,
                    "domains": list(memory_control.internet_learning_domains),
                    "safe_only": True,
                },
            },
        )
        learning_path = write_learning_record(learning_record)
        interaction_record = InteractionRecord(
            timestamp=learning_record.timestamp,
            project_id=self._project_id,
            source=f"commander:{command.source}",
            ui_mode=str(command.context.get("ui_mode", "presence")),
            user_command=command.text,
            transcript=command.text,
            detected_intent=intent.intent,
            selected_agent=plan.selected_agent,
            selected_model=response.model,
            provider=response.provider,
            workflow_steps=list(response.workflow_trace),
            reply_text=response.reply_text,
            speech_text=response.speech_text,
            memory_hits_count=len(response.memory_hits),
            tool_calls_count=len(response.tool_calls),
            success=learning_record.success,
            memory_saved=learning_record.memory_saved,
            training_candidate=learning_record.training_candidate,
            approval_required=response.approval_required,
            risk_level=response.risk_level,
            error=response.error,
            metadata={"learning_path": str(learning_path), "memory_control": memory_control.to_dict()},
        )
        interaction_path = write_interaction_record(self._project_id, interaction_record)
        if learning_record.training_candidate:
            candidate = TrainingCandidate(
                instruction=self._build_training_candidate_instruction(intent, plan, memory_control),
                input=command.text,
                preferred_output=response.reply_text,
                source_interaction_id=learning_record.record_id,
                quality_score=0.7 if learning_record.success else 0.3,
                metadata={"interaction_path": str(interaction_path), "learning_path": str(learning_path), "memory_control": memory_control.to_dict()},
            )
            write_training_candidate(candidate)
        self._event_bus.publish("learning.captured", {"record_id": learning_record.record_id, "intent": intent.intent}, correlation_id=command.command_id, task_id=command.command_id)

    def build_response_envelope(self, **kwargs: Any) -> JarvisResponseEnvelope:
        return build_response_envelope(**kwargs)

    def runtime_status(self) -> dict[str, Any]:
        return self._runtime.status().to_dict()

    def _plan_steps(self, intent: IntentResult, goal: str) -> list[dict[str, Any]]:
        steps = [
            {"step": 1, "action": "understand", "summary": f"Classify owner request as {intent.intent}"},
            {"step": 2, "action": "plan", "summary": f"Route to {self.select_agent(intent, None)}"},
        ]
        if intent.requires_omnira:
            steps.append({"step": 3, "action": "omnira_call", "summary": "Request reasoning from OMNIRA"})
        elif intent.local_command:
            steps.append({"step": 3, "action": "local_runtime", "summary": "Handle safe command locally"})
        else:
            steps.append({"step": 3, "action": "proposal", "summary": "Prepare dry-run output under approval rules"})
        steps.append({"step": 4, "action": "verify", "summary": "Verify and capture learning"})
        return steps

    def _build_agent_tasks(self, intent: IntentResult, goal: str, selected_agent: str) -> list[AgentTask]:
        if intent.intent == "self_code_change":
            return [
                AgentTask(
                    agent="architect",
                    intent="self_code_change",
                    input={"goal": goal, "focus": "scope_impacted_modules"},
                    tools_allowed=["inspect_repo", "search_code"],
                    risk_level="medium",
                    metadata={"stage": "analysis", "summary": "Map impacted modules and contracts"},
                ),
                AgentTask(
                    agent="backend_engineer",
                    intent="self_code_change",
                    input={"goal": goal, "focus": "draft_patch"},
                    tools_allowed=["inspect_repo", "write_file_proposal"],
                    risk_level="high",
                    metadata={"stage": "implementation", "summary": "Prepare supervised backend patch proposal"},
                ),
                AgentTask(
                    agent="reviewer",
                    intent="self_code_change",
                    input={"goal": goal, "focus": "risk_review"},
                    tools_allowed=["inspect_repo"],
                    risk_level="medium",
                    metadata={"stage": "review", "summary": "Review proposal for regressions and policy issues"},
                ),
                AgentTask(
                    agent="test_engineer",
                    intent="self_code_change",
                    input={"goal": goal, "focus": "validation_plan"},
                    tools_allowed=["inspect_repo"],
                    risk_level="medium",
                    metadata={"stage": "verification", "summary": "Define compile, unit, and workflow checks"},
                ),
            ]
        if intent.intent == "self_improve_ui":
            return [
                AgentTask(
                    agent="ui_designer",
                    intent="self_improve_ui",
                    input={"goal": goal, "focus": "visual_direction"},
                    tools_allowed=["inspect_repo"],
                    risk_level="medium",
                    metadata={"stage": "design", "summary": "Define cinematic UI adjustments"},
                ),
                AgentTask(
                    agent="frontend_engineer",
                    intent="self_improve_ui",
                    input={"goal": goal, "focus": "patch_qml_or_tauri"},
                    tools_allowed=["inspect_repo", "write_file_proposal"],
                    risk_level="high",
                    metadata={"stage": "implementation", "summary": "Prepare UI patch proposal"},
                ),
                AgentTask(
                    agent="reviewer",
                    intent="self_improve_ui",
                    input={"goal": goal, "focus": "readability_and_safety_review"},
                    tools_allowed=["inspect_repo"],
                    risk_level="medium",
                    metadata={"stage": "review", "summary": "Review UI proposal against protocol rules"},
                ),
                AgentTask(
                    agent="test_engineer",
                    intent="self_improve_ui",
                    input={"goal": goal, "focus": "launch_checks"},
                    tools_allowed=["inspect_repo"],
                    risk_level="medium",
                    metadata={"stage": "verification", "summary": "Define compile and launch checks"},
                ),
            ]
        if intent.intent == "code_change":
            return [
                AgentTask(
                    agent=selected_agent,
                    intent="code_change",
                    input={"goal": goal, "focus": "draft_patch"},
                    tools_allowed=["inspect_repo", "write_file_proposal"],
                    risk_level="high",
                    metadata={"stage": "implementation", "summary": "Prepare supervised code patch proposal"},
                ),
                AgentTask(
                    agent="test_engineer",
                    intent="code_change",
                    input={"goal": goal, "focus": "validation_plan"},
                    tools_allowed=["inspect_repo"],
                    risk_level="medium",
                    metadata={"stage": "verification", "summary": "Define verification steps before apply"},
                ),
            ]
        return []

    def _control_requirements_for_intent(self, intent_name: str) -> dict[str, Any]:
        if intent_name in {"self_code_change", "self_improve_ui", "code_change"}:
            return {
                "owner_approval_required_before_apply": True,
                "owner_can_pause": True,
                "owner_can_kill": True,
                "rollback_required": True,
            }
        return {
            "owner_can_pause": True,
            "owner_can_kill": True,
        }

    def _call_omnira(self, plan: ExecutionPlan) -> dict[str, Any]:
        client = create_openai_client(self._config)
        if not isinstance(client, OmniraClient):
            return {
                "success": True,
                "reply_text": "OMNIRA routing is configured through the existing backend adapter, but the current backend is not the local OMNIRA adapter. I stayed in controlled local mode.",
                "speech_text": "I stayed in controlled local mode.",
                "state": "speaking",
                "agent": plan.selected_agent,
                "model": str(plan.metadata.get("resolved_model") or self._config.model),
                "provider": self._config.backend,
                "workflow_trace": [{"step": "omnira.route", "status": "skipped", "detail": "backend is not OMNIRA adapter"}],
                "metadata": {"placeholder": True},
            }

        self._event_bus.publish("omnira.request.started", {"goal": plan.goal}, correlation_id=plan.metadata.get("command_id", ""), task_id=plan.metadata.get("command_id", ""))
        preferred_agent = resolve_omnira_agent_name(plan.selected_agent, dynamic_routing=True)
        response = client.responses.create(
            model=str(plan.metadata.get("resolved_model") or "") or None,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": "You are OMNIRA supporting the Jarvis Commander. Remain concise, owner-controlled, and approval-aware."}]},
                {"role": "user", "content": [{"type": "input_text", "text": plan.goal}]},
            ],
            max_output_tokens=int(plan.metadata.get("max_output_tokens") or 500),
            reasoning={"effort": str(plan.metadata.get("reasoning_effort") or self._config.reasoning_effort)},
            preferred_agent=preferred_agent,
        )
        normalized = response.response
        self._event_bus.publish("omnira.response.received", {"model": normalized.model, "agent": normalized.agent}, correlation_id=plan.metadata.get("command_id", ""), task_id=plan.metadata.get("command_id", ""))
        return {
            "success": True,
            "reply_text": normalized.reply_text,
            "speech_text": normalized.speech_text,
            "state": normalized.state,
            "intent": normalized.intent,
            "agent": normalized.agent or plan.selected_agent,
            "model": normalized.model,
            "provider": normalized.provider,
            "memory_hits": normalized.memory_hits,
            "tool_calls": normalized.tool_calls,
            "workflow_trace": normalized.workflow_trace or [{"step": "omnira", "status": "ok", "detail": "response received"}],
            "visualization": normalized.visualization,
            "safety_flags": normalized.safety_flags,
            "metadata": dict(normalized.metadata),
        }

    def _dry_run_proposal(self, plan: ExecutionPlan) -> dict[str, Any]:
        impact = self._repo_intelligence.impact_report(plan.goal)
        plan.metadata["files_affected"] = list(impact.files)
        proposal_details: dict[str, Any] = {}
        workflow_trace = [{"step": "repo.scan", "status": "ok", "detail": impact.summary}]
        tool_calls = [
            {"name": "inspect_repo", "status": "completed"},
            {"name": "write_file_proposal", "status": "prepared"},
        ]
        reply_text: str
        validation_steps: list[str] = []
        placeholder = False
        try:
            proposal = self._code_patch_engine.prepare_proposal(plan.goal, plan.selected_agent)
            proposal_details = {
                "proposal_id": proposal.proposal_id,
                "summary_path": proposal.summary_path,
                "patch_path": proposal.patch_path,
                "raw_output_path": proposal.raw_output_path,
                "diff_summary": proposal.diff_summary,
                "patch_preview": proposal.patch_preview,
                "validation_message": proposal.validation_message,
            }
            reply_text = (
                f"Prepared a supervised patch proposal for '{plan.goal}'. "
                f"Impact files: {len(impact.files)}. Diff summary: {proposal.diff_summary}. "
                "Approval will be required before any apply, commit, or destructive step."
            )
            workflow_trace.extend(
                [
                    {"step": "proposal.generate", "status": "ok", "detail": proposal.proposal_id},
                    {"step": "proposal.validate", "status": "ok", "detail": proposal.validation_message},
                ]
            )
            validation_steps.append(proposal.validation_message)
        except Exception as exc:
            placeholder = True
            proposal_details = {"error": str(exc)}
            reply_text = (
                f"Prepared a dry-run implementation proposal for '{plan.goal}', but no patch was generated yet. "
                f"Likely impacted files: {len(impact.files)}. Approval will still be required before apply."
            )
            workflow_trace.append({"step": "proposal.generate", "status": "warning", "detail": str(exc)})
        return {
            "success": True,
            "reply_text": reply_text,
            "speech_text": "I prepared a supervised proposal summary.",
            "state": "thinking",
            "agent": plan.selected_agent,
            "provider": "local-planner",
            "tool_calls": tool_calls,
            "workflow_trace": workflow_trace,
            "safety_flags": ["approval_required_before_apply"],
            "metadata": {
                "placeholder": placeholder,
                "files_affected": impact.files,
                "impact_report": impact.to_dict(),
                "proposal": proposal_details,
                "apply_requires_approval": True,
                "tests_to_run": ["python -m py_compile agenthub\\*.py", "python -m unittest tests.test_commander_phase1_2"],
                "rollback_plan": plan.rollback_plan,
            },
            "verification": validation_steps,
        }

    def _run_self_code_change_workflow(self, plan: ExecutionPlan) -> dict[str, Any]:
        base = self._dry_run_proposal(plan)
        workflow_payload = {
            "workflow_type": "self_code_change",
            "plan_goal": plan.goal,
            "workflow_steps": list(plan.metadata.get("workflow_steps") or list(SELF_CODE_WORKFLOW_STEPS)),
            "agent_tasks": [task.to_dict() for task in plan.agent_tasks],
            "validation_gates": list(plan.verification_steps),
            "control_requirements": dict(plan.control_requirements),
            "risk": plan.risk_level,
            "approval_requirement": "Approval is required before apply, commit, deploy, delete, or any destructive action.",
            "tests_to_run": [
                "python -m py_compile agenthub\\*.py",
                "python -m unittest tests.test_commander_phase1_2 tests.test_phase3_tooling tests.test_phase4_workflows",
            ],
            "rollback_plan": list(plan.rollback_plan),
            "files_to_change": list(base.get("metadata", {}).get("files_affected", [])),
            "patch_proposal": dict(base.get("metadata", {}).get("proposal", {})),
        }
        base["reply_text"] = (
            f"Self-code-change dry run prepared for '{plan.goal}'. "
            f"Risk: {plan.risk_level}. Specialist tasks: {len(workflow_payload['agent_tasks'])}. Files identified: {len(workflow_payload['files_to_change'])}. "
            "I can propose and validate changes, but I will not apply them without approval."
        )
        base["speech_text"] = "I prepared a self-code-change dry run."
        base["workflow_trace"] = [
            {"step": "workflow.self_code_change", "status": "ok", "detail": "dry-run workflow prepared"},
            *list(base.get("workflow_trace") or []),
        ]
        base["metadata"] = {
            **dict(base.get("metadata") or {}),
            **workflow_payload,
        }
        return base

    def _run_self_improve_ui_workflow(self, plan: ExecutionPlan) -> dict[str, Any]:
        base = self._dry_run_proposal(plan)
        files = list(base.get("metadata", {}).get("files_affected", []))
        ui_files = [path for path in files if path.endswith(".qml") or "desktop" in path.lower() or "qml/" in path.lower()]
        design_changes = self._derive_ui_design_changes(plan.goal)
        workflow_payload = {
            "workflow_type": "self_improve_ui",
            "plan_goal": plan.goal,
            "workflow_steps": list(plan.metadata.get("workflow_steps") or list(SELF_UI_WORKFLOW_STEPS)),
            "agent_tasks": [task.to_dict() for task in plan.agent_tasks],
            "validation_gates": list(plan.verification_steps),
            "control_requirements": dict(plan.control_requirements),
            "ui_protocol_rules": list(plan.metadata.get("ui_protocol_rules") or list(UI_PROTOCOL_RULES)),
            "current_ui_files": ui_files,
            "design_changes": design_changes,
            "before_after_notes": {
                "before": "Current UI state should be summarized from existing QML/PySide surfaces before any apply step.",
                "after": "After approval and apply, launch and compile checks should confirm the intended visual behavior.",
            },
            "approval_requirement": "Approval is required before applying UI changes or launching any destructive or persistent modifications.",
            "tests_to_run": [
                "python -m py_compile agenthub\\desktop_qt.py agenthub\\commander.py",
                "python -m unittest tests.test_commander_phase1_2 tests.test_phase3_tooling tests.test_phase4_workflows",
            ],
            "patch_proposal": dict(base.get("metadata", {}).get("proposal", {})),
        }
        base["reply_text"] = (
            f"Self-UI-improvement dry run prepared for '{plan.goal}'. "
            f"Specialist tasks: {len(workflow_payload['agent_tasks'])}. UI files identified: {len(ui_files)}. Proposed design changes: {len(design_changes)}. "
            "I can propose and validate the UI patch, but I will not apply it without approval."
        )
        base["speech_text"] = "I prepared a self UI improvement dry run."
        base["workflow_trace"] = [
            {"step": "workflow.self_improve_ui", "status": "ok", "detail": "dry-run UI workflow prepared"},
            {"step": "ui.protocol", "status": "ok", "detail": f"{len(workflow_payload['ui_protocol_rules'])} rules checked"},
            *list(base.get("workflow_trace") or []),
        ]
        base["metadata"] = {
            **dict(base.get("metadata") or {}),
            **workflow_payload,
        }
        return base

    def _run_repo_analysis(self, plan: ExecutionPlan) -> dict[str, Any]:
        tool_result = self._tool_runtime.execute(ToolRequest(tool_name="inspect_repo", action="inspect", args={"project": self._project_path}))
        impact = self._repo_intelligence.impact_report(plan.goal)
        plan.metadata["files_affected"] = list(impact.files)
        return {
            "success": tool_result.success,
            "reply_text": tool_result.output or impact.summary,
            "speech_text": "Repo analysis is ready.",
            "state": "speaking",
            "agent": "repo_analyst",
            "provider": "local-repo-intelligence",
            "tool_calls": [{"name": "inspect_repo", "status": "completed" if tool_result.success else "failed"}],
            "workflow_trace": [
                {"step": "repo.scan", "status": "ok" if tool_result.success else "failed", "detail": impact.summary},
                {"step": "impact.report", "status": "ok", "detail": ", ".join(impact.files[:5]) or "no likely files"},
            ],
            "metadata": {"repo_summary": tool_result.metadata, "impact_report": impact.to_dict(), "files_affected": impact.files},
            "verification": ["local_repo_scan"],
        }

    def _derive_ui_design_changes(self, goal: str) -> list[str]:
        lowered = goal.lower()
        changes: list[str] = []
        if any(token in lowered for token in ("presence", "minimal", "clutter")):
            changes.append("Keep Presence Mode minimal and reduce non-essential surfaces")
        if any(token in lowered for token in ("orb", "core", "reactor")):
            changes.append("Preserve the orb as the primary visual focus")
        if any(token in lowered for token in ("readable", "text", "transcript")):
            changes.append("Improve transcript and status readability")
        if any(token in lowered for token in ("dock", "controls", "button")):
            changes.append("Clarify the bottom control dock and button states")
        if any(token in lowered for token in ("chip", "status")):
            changes.append("Keep status chips compact and meaningful")
        if not changes:
            changes.append("Refine composition, readability, and cinematic restraint without changing architecture")
        return changes

    def _extract_memory_payload(self, text: str) -> str:
        lowered = text.lower()
        for prefix in ("remember this", "save this as rule", "prefer this style"):
            if lowered.startswith(prefix):
                payload = text[len(prefix) :].strip(" :.-")
                return payload or text
        return text

    def _owner_profile_signal(self, intent: IntentResult, command: OwnerCommand, memory_control: Any) -> dict[str, Any]:
        if not getattr(memory_control, "profile_learning_enabled", False):
            return {"enabled": False}
        return {
            "enabled": True,
            "intent": intent.intent,
            "source": command.source,
            "ui_mode": str(command.context.get("ui_mode", "presence")),
            "explicit_preference": intent.intent == "memory_save",
        }

    def _build_training_candidate_instruction(self, intent: IntentResult, plan: ExecutionPlan, memory_control: Any) -> str:
        parts = [
            f"Handle intent: {intent.intent}",
            f"Workflow: {str(plan.metadata.get('workflow_name') or intent.intent)}",
            f"Risk level: {plan.risk_level}",
            "Stay approval-aware and prefer efficient local execution before escalating compute.",
        ]
        if getattr(memory_control, "internet_learning_enabled", False):
            parts.append(
                "When external knowledge is needed, use only owner-approved safe domains: "
                + ", ".join(list(getattr(memory_control, "internet_learning_domains", []))[:8])
                + "."
            )
        if getattr(memory_control, "pinned_model", ""):
            parts.append(f"Pinned model preference: {getattr(memory_control, 'pinned_model', '')}.")
        return " ".join(parts)

    def _learning_readiness_status(self) -> dict[str, Any]:
        memory_control = load_memory_control_state()
        status = self._runtime.refresh_status(active_agent="omnira_bridge")
        learning_count = len(iter_json_like_files(BASE_DIR / "data" / "learning"))
        candidate_count = len(iter_json_like_files(BASE_DIR / "data" / "training_candidates"))
        readiness = "ready" if status.omnira_online and memory_control.training_enabled and memory_control.observation_enabled else "partial"
        reply = (
            f"Learning readiness is {readiness}. "
            f"Backend is {'online' if status.omnira_online else 'offline'}. "
            f"Training is {'on' if memory_control.training_enabled else 'off'}. "
            f"Observation is {'on' if memory_control.observation_enabled else 'off'}. "
            f"Compute mode is {memory_control.compute_mode}. "
            f"Pinned model is {memory_control.pinned_model or 'not set'}. "
            f"Learning records: {learning_count}. Training candidates: {candidate_count}."
        )
        return {
            "success": True,
            "reply_text": reply,
            "speech_text": "Learning readiness is ready.",
            "state": "speaking",
            "agent": "memory",
            "provider": "local-memory",
            "workflow_trace": [{"step": "learning.readiness", "status": "ok", "detail": readiness}],
            "metadata": {
                "memory_control": memory_control.to_dict(),
                "runtime_status": status.to_dict(),
                "learning_records": learning_count,
                "training_candidates": candidate_count,
                "readiness": readiness,
            },
        }

    def _normalize_verification_metadata(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"checks": [str(item) for item in value]}
        if value is None:
            return {}
        return {"value": value}

    def _normalize_mapping(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"items": [str(item) for item in value]}
        if value is None:
            return {}
        return {"value": value}
from __future__ import annotations

from collections.abc import Iterator

from app.agents.service import AGENTS
from app.memory.service import MemoryService
from app.models.router import ModelRouter
from app.models.service import ModelService
from app.safety.engine import SafetyEngine
from app.schemas import ChatResponse, MemoryRecord, ModelRequest, ModelStreamEvent
from app.telemetry.logger import get_logger


class OmniraPrimeOrchestrator:
    def __init__(self) -> None:
        self.logger = get_logger("omnira.prime")
        self.memory = MemoryService()
        self.router = ModelRouter()
        self.model_service = ModelService()
        self.safety = SafetyEngine()

    def run(
        self,
        message: str,
        conversation_id: str | None = None,
        metadata: dict | None = None,
        system_prompt: str | None = None,
        preferred_model: str | None = None,
        preferred_agent: str | None = None,
    ) -> ChatResponse:
        metadata = metadata or {}
        decision_path: list[str] = []
        decision_path.append("accept-user-message")

        route = self.router.route(message, metadata)
        if preferred_agent or preferred_model:
            resolved_agent = preferred_agent or route.agent
            resolved_model = preferred_model
            if resolved_model is None:
                preferred_profile = AGENTS.get(resolved_agent)
                if preferred_profile is not None:
                    resolved_model = preferred_profile.model
            if resolved_model is None:
                resolved_model = route.model
            route = route.model_copy(
                update={
                    "agent": resolved_agent,
                    "model": resolved_model,
                    "reasoning": "Preferred agent/model override applied for external orchestrator integration.",
                }
            )
            decision_path.append(f"classify-intent:override:{route.agent}")
        else:
            decision_path.append(f"classify-intent:{route.agent}")

        external_orchestrator_request = bool(preferred_agent or preferred_model or metadata.get("source") == "jarvis")
        if external_orchestrator_request:
            memory_hits = []
            decision_path.append("retrieve-memory:external-bypass")
        else:
            memory_hits = self.memory.search(message)
            decision_path.append(f"retrieve-memory:{len(memory_hits)}-hits")

        agent = AGENTS.get(route.agent, AGENTS["omnira-lite"])
        requested_tools = list(agent.allowed_tools)
        if any(keyword in message.lower() for keyword in ("run", "execute", "deploy", "open")):
            decision_path.append("tools-needed:true")
        else:
            decision_path.append("tools-needed:false")
            requested_tools = []

        safety = self.safety.evaluate(message, tools=requested_tools)
        decision_path.append(f"safety-check:{safety.risk_level}")
        memory_hit_payload = self._memory_hits_payload(memory_hits)
        tool_call_payload = self._tool_call_payload(requested_tools, safety.requires_approval)
        if not safety.allowed:
            return ChatResponse(
                response="Request blocked by safety policy.",
                reply_text="Request blocked by safety policy.",
                speech_text="Request blocked by safety policy.",
                state="error",
                intent=route.agent,
                model=route.model,
                agent=route.agent,
                provider="policy",
                confidence=route.confidence,
                decision_path=decision_path,
                memory_hits=memory_hit_payload,
                tool_calls=tool_call_payload,
                workflow_trace=self._workflow_trace_payload(decision_path),
                visualization=self._visualization_payload(route.agent, "Request blocked by safety policy.", memory_hit_payload, decision_path),
                safety_flags=safety.flags,
                approval_required=False,
                risk_level=safety.risk_level,
                error={"kind": "policy", "message": "Request blocked by safety policy."},
                metadata={"conversation_id": conversation_id},
            )

        prompt = message
        if memory_hits:
            memory_context = "\n".join(record.content for record in memory_hits[:3])
            prompt = f"Relevant memory:\n{memory_context}\n\nUser request:\n{message}"

        model_response = self.model_service.generate(
            ModelRequest(
                prompt=prompt,
                system_prompt=system_prompt or agent.system_prompt,
                model=route.model,
                tools_allowed=requested_tools,
                metadata={"agent": route.agent, "conversation_id": conversation_id, **metadata},
            )
        )
        decision_path.append(f"model-selected:{route.model}")
        decision_path.append(f"provider:{model_response.provider}")
        if safety.requires_approval:
            decision_path.append("approval-required:true")

        memory_record = MemoryRecord(
            type="conversation",
            title=(message[:60] or "Conversation event").strip(),
            content=message,
            tags=[route.agent, route.model],
            source="chat",
            importance=2,
            metadata={"conversation_id": conversation_id or "default"},
        )
        self.memory.save(memory_record)
        decision_path.append("log-decision-path")
        self.logger.info("decision_path=%s", " > ".join(decision_path))

        return ChatResponse(
            response=model_response.content,
            reply_text=model_response.content,
            speech_text=model_response.content,
            state="approval_required" if safety.requires_approval else "speaking",
            intent=route.agent,
            model=model_response.model_used,
            agent=route.agent,
            provider=model_response.provider,
            confidence=route.confidence,
            decision_path=decision_path,
            memory_hits=memory_hit_payload,
            tool_calls=tool_call_payload,
            workflow_trace=self._workflow_trace_payload(decision_path),
            visualization=self._visualization_payload(route.agent, model_response.content, memory_hit_payload, decision_path),
            safety_flags=safety.flags,
            approval_required=safety.requires_approval,
            risk_level=safety.risk_level,
            metadata={
                "conversation_id": conversation_id,
                "matched_keywords": route.matched_keywords,
                "requires_approval": safety.requires_approval,
                "confidence": route.confidence,
                "provider_metadata": model_response.metadata,
            },
        )

    def stream(
        self,
        message: str,
        conversation_id: str | None = None,
        metadata: dict | None = None,
        system_prompt: str | None = None,
        preferred_model: str | None = None,
        preferred_agent: str | None = None,
    ) -> Iterator[tuple[ModelStreamEvent, dict[str, object]]]:
        metadata = metadata or {}
        decision_path: list[str] = []
        decision_path.append("accept-user-message")

        route = self.router.route(message, metadata)
        if preferred_agent or preferred_model:
            resolved_agent = preferred_agent or route.agent
            resolved_model = preferred_model
            if resolved_model is None:
                preferred_profile = AGENTS.get(resolved_agent)
                if preferred_profile is not None:
                    resolved_model = preferred_profile.model
            if resolved_model is None:
                resolved_model = route.model
            route = route.model_copy(
                update={
                    "agent": resolved_agent,
                    "model": resolved_model,
                    "reasoning": "Preferred agent/model override applied for external orchestrator integration.",
                }
            )
            decision_path.append(f"classify-intent:override:{route.agent}")
        else:
            decision_path.append(f"classify-intent:{route.agent}")

        external_orchestrator_request = bool(preferred_agent or preferred_model or metadata.get("source") == "jarvis")
        if external_orchestrator_request:
            memory_hits = []
            decision_path.append("retrieve-memory:external-bypass")
        else:
            memory_hits = self.memory.search(message)
            decision_path.append(f"retrieve-memory:{len(memory_hits)}-hits")

        agent = AGENTS.get(route.agent, AGENTS["omnira-lite"])
        requested_tools = list(agent.allowed_tools)
        if any(keyword in message.lower() for keyword in ("run", "execute", "deploy", "open")):
            decision_path.append("tools-needed:true")
        else:
            decision_path.append("tools-needed:false")
            requested_tools = []

        safety = self.safety.evaluate(message, tools=requested_tools)
        decision_path.append(f"safety-check:{safety.risk_level}")
        memory_hit_payload = self._memory_hits_payload(memory_hits)
        tool_call_payload = self._tool_call_payload(requested_tools, safety.requires_approval)
        if not safety.allowed:
            yield (
                ModelStreamEvent(
                    delta="Request blocked by safety policy.",
                    done=True,
                    model_used=route.model,
                    provider="policy",
                    metadata={
                        "reply_text": "Request blocked by safety policy.",
                        "speech_text": "Request blocked by safety policy.",
                        "state": "error",
                        "intent": route.agent,
                        "confidence": route.confidence,
                        "decision_path": decision_path,
                        "memory_hits": memory_hit_payload,
                        "tool_calls": tool_call_payload,
                        "workflow_trace": self._workflow_trace_payload(decision_path),
                        "visualization": self._visualization_payload(route.agent, "Request blocked by safety policy.", memory_hit_payload, decision_path),
                        "safety_flags": safety.flags,
                        "approval_required": False,
                        "risk_level": safety.risk_level,
                        "error": {"kind": "policy", "message": "Request blocked by safety policy."},
                    },
                ),
                {
                    "agent": route.agent,
                    "intent": route.agent,
                    "confidence": route.confidence,
                    "decision_path": decision_path,
                    "memory_hits": memory_hit_payload,
                    "tool_calls": tool_call_payload,
                    "workflow_trace": self._workflow_trace_payload(decision_path),
                    "visualization": self._visualization_payload(route.agent, "Request blocked by safety policy.", memory_hit_payload, decision_path),
                    "safety_flags": safety.flags,
                    "risk_level": safety.risk_level,
                    "conversation_id": conversation_id,
                    "matched_keywords": route.matched_keywords,
                    "requires_approval": False,
                },
            )
            return

        prompt = message
        if memory_hits:
            memory_context = "\n".join(record.content for record in memory_hits[:3])
            prompt = f"Relevant memory:\n{memory_context}\n\nUser request:\n{message}"

        decision_path.append(f"model-selected:{route.model}")
        stream_request = ModelRequest(
            prompt=prompt,
            system_prompt=system_prompt or agent.system_prompt,
            model=route.model,
            tools_allowed=requested_tools,
            metadata={"agent": route.agent, "conversation_id": conversation_id, **metadata},
        )
        final_provider = ""
        for event in self.model_service.stream_generate(stream_request):
            final_provider = event.provider or final_provider
            if event.done and final_provider:
                decision_path.append(f"provider:{final_provider}")
                if safety.requires_approval:
                    decision_path.append("approval-required:true")
                memory_record = MemoryRecord(
                    type="conversation",
                    title=(message[:60] or "Conversation event").strip(),
                    content=message,
                    tags=[route.agent, route.model],
                    source="chat",
                    importance=2,
                    metadata={"conversation_id": conversation_id or "default"},
                )
                self.memory.save(memory_record)
                decision_path.append("log-decision-path")
                self.logger.info("decision_path=%s", " > ".join(decision_path))
            yield (
                event,
                {
                    "agent": route.agent,
                    "intent": route.agent,
                    "confidence": route.confidence,
                    "decision_path": decision_path,
                    "memory_hits": memory_hit_payload,
                    "tool_calls": tool_call_payload,
                    "workflow_trace": self._workflow_trace_payload(decision_path),
                    "visualization": self._visualization_payload(route.agent, "", memory_hit_payload, decision_path),
                    "safety_flags": safety.flags,
                    "risk_level": safety.risk_level,
                    "conversation_id": conversation_id,
                    "matched_keywords": route.matched_keywords,
                    "requires_approval": safety.requires_approval,
                },
            )

    def _memory_hits_payload(self, records: list[MemoryRecord]) -> list[dict[str, object]]:
        payload: list[dict[str, object]] = []
        for record in records[:3]:
            payload.append(
                {
                    "title": record.title,
                    "source": record.source,
                    "content": record.content[:180],
                    "tags": list(record.tags),
                }
            )
        return payload

    def _tool_call_payload(self, requested_tools: list[str], approval_required: bool) -> list[dict[str, str]]:
        status = "approval_required" if approval_required else "available"
        return [{"name": tool, "status": status} for tool in requested_tools]

    def _workflow_trace_payload(self, decision_path: list[str]) -> list[dict[str, str]]:
        return [{"step": step, "status": "ok", "detail": step} for step in decision_path]

    def _visualization_payload(
        self,
        intent: str,
        reply_text: str,
        memory_hits: list[dict[str, object]],
        decision_path: list[str],
    ) -> dict[str, object]:
        if memory_hits:
            return {
                "type": "memory_used",
                "title": "Memory Used",
                "items": memory_hits,
            }
        return {
            "type": "status_cards",
            "title": "OMNIRA Response",
            "items": [
                {"label": "Intent", "value": intent},
                {"label": "Decision Path", "value": " > ".join(decision_path[:3]) or "pending"},
                {"label": "Reply", "value": reply_text[:160] if reply_text else "Streaming"},
            ],
        }

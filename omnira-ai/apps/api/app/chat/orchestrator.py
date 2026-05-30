from __future__ import annotations

from app.agents.service import AGENTS
from app.memory.service import MemoryService
from app.models.router import ModelRouter
from app.models.service import ModelService
from app.safety.engine import SafetyEngine
from app.schemas import ChatResponse, MemoryRecord, ModelRequest
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

        route = self.router.route(message)
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
        if not safety.allowed:
            return ChatResponse(
                response="Request blocked by safety policy.",
                model=route.model,
                agent=route.agent,
                provider="policy",
                decision_path=decision_path,
                safety_flags=safety.flags,
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
            model=model_response.model_used,
            agent=route.agent,
            provider=model_response.provider,
            decision_path=decision_path,
            safety_flags=safety.flags,
            metadata={
                "conversation_id": conversation_id,
                "matched_keywords": route.matched_keywords,
                "requires_approval": safety.requires_approval,
            },
        )

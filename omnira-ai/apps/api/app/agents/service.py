from __future__ import annotations

from dataclasses import dataclass

from app.models.service import ModelService
from app.schemas import AgentRunResponse, ModelRequest


@dataclass(frozen=True)
class BaseAgent:
    name: str
    purpose: str
    allowed_tools: list[str]
    risk_level: str
    system_prompt: str
    model: str

    def run(self, message: str, model_service: ModelService) -> AgentRunResponse:
        response = model_service.generate(
            ModelRequest(
                prompt=message,
                system_prompt=self.system_prompt,
                model=self.model,
                tools_allowed=self.allowed_tools,
                metadata={"agent": self.name},
            )
        )
        return AgentRunResponse(
            agent=self.name,
            result=response.content,
            model=response.model_used,
            provider=response.provider,
            metadata={"purpose": self.purpose, "risk_level": self.risk_level},
        )


AGENTS: dict[str, BaseAgent] = {
    "omnira-prime": BaseAgent("omnira-prime", "Central orchestrator for mixed tasks.", ["memory", "rag"], "medium", "You are OMNIRA Prime, the orchestrator.", "omnira-platform-qwen-7b-v0.1"),
    "omnira-lite": BaseAgent("omnira-lite", "Fast personal assistant for daily tasks.", [], "low", "You are OMNIRA Lite, a fast personal assistant who is concise, helpful, and practical.", "omnira-lite-qwen-3b-v0.1"),
    "omnira-code": BaseAgent("omnira-code", "Coding and repository assistant.", ["filesystem", "github"], "medium", "You are OMNIRA Code, focused on software engineering tasks.", "omnira-code-qwen-coder-7b-v0.1"),
    "omnira-platform": BaseAgent("omnira-platform", "Platform, DevOps, Azure, Kubernetes, and Terraform assistant.", ["azure", "terraform", "kubernetes", "shell"], "high", "You are OMNIRA Platform, focused on cloud and platform operations.", "omnira-platform-qwen-7b-v0.1"),
    "omnira-bharat": BaseAgent("omnira-bharat", "Hindi, Hinglish, and India-context assistant.", [], "low", "You are OMNIRA Bharat, optimized for Indian context and language nuance.", "omnira-bharat-qwen-7b-v0.1"),
    "omnira-coach": BaseAgent("omnira-coach", "Career, learning, and habit coaching assistant.", [], "low", "You are OMNIRA Coach, practical and structured.", "omnira-coach-qwen-7b-v0.1"),
    "omnira-research": BaseAgent("omnira-research", "Document intelligence and deep research assistant.", ["rag"], "medium", "You are OMNIRA Research, rigorous and evidence-seeking.", "omnira-research-qwen-14b-v0.1"),
    "omnira-shield": BaseAgent("omnira-shield", "Defensive security learning assistant.", [], "high", "You are OMNIRA Shield, defensive and safety bounded.", "omnira-shield-qwen-7b-v0.1"),
    "omnira-trade": BaseAgent("omnira-trade", "Trading research and strategy assistant.", ["market-data"], "high", "You are OMNIRA Trade, analytical and risk aware.", "omnira-trade-qwen-7b-v0.1"),
}


class AgentService:
    def __init__(self) -> None:
        self.model_service = ModelService()

    def list_agents(self) -> list[dict[str, str]]:
        return [{"name": agent.name, "purpose": agent.purpose} for agent in AGENTS.values()]

    def run(self, name: str, message: str) -> AgentRunResponse:
        agent = AGENTS.get(name)
        if agent is None:
            agent = AGENTS["omnira-lite"]
        return agent.run(message=message, model_service=self.model_service)

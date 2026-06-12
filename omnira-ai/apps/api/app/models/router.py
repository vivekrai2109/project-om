from __future__ import annotations

from dataclasses import dataclass

from app.schemas import RouteResponse


@dataclass(frozen=True)
class RouteRule:
    agent: str
    model: str
    keywords: tuple[str, ...]
    reasoning: str


ROUTE_RULES: tuple[RouteRule, ...] = (
    RouteRule(
        agent="omnira-lite",
        model="omnira-lite-qwen-3b-v0.1",
        keywords=("remind", "schedule", "calendar", "todo", "organize", "personal"),
        reasoning="General personal-assistant tasks should use OMNIRA Lite.",
    ),
    RouteRule(
        agent="omnira-code",
        model="omnira-code-qwen-coder-7b-v0.1",
        keywords=("code", "debug", "bug", "python", "typescript", "repo", "api"),
        reasoning="Coding and repository tasks should use OMNIRA Code.",
    ),
    RouteRule(
        agent="omnira-platform",
        model="omnira-platform-qwen-7b-v0.1",
        keywords=("azure", "terraform", "kubernetes", "docker", "sre", "ci/cd", "pipeline"),
        reasoning="Platform and infra tasks should use OMNIRA Platform.",
    ),
    RouteRule(
        agent="omnira-bharat",
        model="omnira-bharat-qwen-7b-v0.1",
        keywords=("hindi", "hinglish", "india", "indian", "bharat"),
        reasoning="Hindi, Hinglish, and India-context tasks should use OMNIRA Bharat.",
    ),
    RouteRule(
        agent="omnira-coach",
        model="omnira-coach-qwen-7b-v0.1",
        keywords=("career", "learn", "habit", "communication", "study", "interview"),
        reasoning="Coaching and growth tasks should use OMNIRA Coach.",
    ),
    RouteRule(
        agent="omnira-research",
        model="omnira-research-qwen-14b-v0.1",
        keywords=("research", "document", "paper", "analyze", "summary", "rag"),
        reasoning="Document-heavy and research tasks should use OMNIRA Research.",
    ),
    RouteRule(
        agent="omnira-shield",
        model="omnira-shield-qwen-7b-v0.1",
        keywords=("security", "vulnerability", "defense", "malware", "incident", "safe cyber"),
        reasoning="Defensive security tasks should use OMNIRA Shield.",
    ),
    RouteRule(
        agent="omnira-trade",
        model="omnira-trade-qwen-7b-v0.1",
        keywords=("trade", "trading", "market", "portfolio", "strategy", "stocks"),
        reasoning="Trading research tasks should use OMNIRA Trade.",
    ),
)

COMPLEXITY_KEYWORDS = ("and", "orchestrate", "compare", "plan", "multi-step", "complex")

MODEL_AGENT_MAP = {
    "omnira-lite-qwen-3b-v0.1": "omnira-lite",
    "omnira-code-qwen-coder-7b-v0.1": "omnira-code",
    "omnira-platform-qwen-7b-v0.1": "omnira-platform",
    "omnira-reasoning-qwen-7b-v0.1": "omnira-prime",
    "omnira-bharat-qwen-7b-v0.1": "omnira-bharat",
    "omnira-coach-qwen-7b-v0.1": "omnira-coach",
    "omnira-research-qwen-14b-v0.1": "omnira-research",
    "omnira-shield-qwen-7b-v0.1": "omnira-shield",
    "omnira-trade-qwen-7b-v0.1": "omnira-trade",
}


class ModelRouter:
    def route(self, message: str, metadata: dict | None = None) -> RouteResponse:
        metadata = metadata or {}
        lowered = message.lower()
        matched: list[str] = []
        best_rule: RouteRule | None = None
        pinned_model = str(metadata.get("pinned_model") or "").strip()
        compute_mode = str(metadata.get("compute_mode") or "balanced").strip().lower() or "balanced"

        if pinned_model:
            return RouteResponse(
                agent=MODEL_AGENT_MAP.get(pinned_model, "omnira-lite"),
                model=pinned_model,
                confidence=0.99,
                matched_keywords=[],
                reasoning="Pinned model preference applied from Jarvis owner control.",
            )

        for rule in ROUTE_RULES:
            hits = [keyword for keyword in rule.keywords if keyword in lowered]
            if hits and len(hits) > len(matched):
                matched = hits
                best_rule = rule

        is_complex = sum(1 for keyword in COMPLEXITY_KEYWORDS if keyword in lowered) >= 2
        if best_rule is None:
            if compute_mode == "lean":
                return RouteResponse(
                    agent="omnira-lite",
                    model="omnira-lite-qwen-3b-v0.1",
                    confidence=0.62,
                    matched_keywords=[],
                    reasoning="Lean compute mode forces the lightweight local assistant path when no stronger route match exists.",
                )
            return RouteResponse(
                agent="omnira-lite",
                model="omnira-lite-qwen-3b-v0.1",
                confidence=0.55,
                matched_keywords=[],
                reasoning="Defaulting to OMNIRA Lite as the personal-assistant entrypoint for simple general tasks.",
            )

        if compute_mode == "lean":
            return RouteResponse(
                agent=best_rule.agent,
                model="omnira-lite-qwen-3b-v0.1" if best_rule.agent in {"omnira-research", "omnira-prime"} else best_rule.model,
                confidence=min(0.9, 0.58 + 0.08 * len(matched)),
                matched_keywords=matched,
                reasoning="Lean compute mode biases routing toward lighter local models.",
            )

        if is_complex or len(matched) >= 3:
            return RouteResponse(
                agent="omnira-prime",
                model="omnira-reasoning-qwen-7b-v0.1",
                confidence=0.75,
                matched_keywords=matched,
                reasoning="Complex or mixed tasks escalate to OMNIRA Prime on the local reasoning model.",
            )

        return RouteResponse(
            agent=best_rule.agent,
            model=best_rule.model,
            confidence=min(0.95, 0.6 + 0.1 * len(matched)),
            matched_keywords=matched,
            reasoning=best_rule.reasoning,
        )

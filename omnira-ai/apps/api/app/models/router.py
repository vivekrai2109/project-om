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


class ModelRouter:
    def route(self, message: str) -> RouteResponse:
        lowered = message.lower()
        matched: list[str] = []
        best_rule: RouteRule | None = None

        for rule in ROUTE_RULES:
            hits = [keyword for keyword in rule.keywords if keyword in lowered]
            if hits and len(hits) > len(matched):
                matched = hits
                best_rule = rule

        is_complex = sum(1 for keyword in COMPLEXITY_KEYWORDS if keyword in lowered) >= 2
        if best_rule is None:
            return RouteResponse(
                agent="omnira-lite",
                model="omnira-lite-qwen-3b-v0.1",
                confidence=0.55,
                matched_keywords=[],
                reasoning="Defaulting to OMNIRA Lite as the personal-assistant entrypoint for simple general tasks.",
            )

        if is_complex or len(matched) >= 3:
            return RouteResponse(
                agent="omnira-prime",
                model="omnira-platform-qwen-7b-v0.1",
                confidence=0.75,
                matched_keywords=matched,
                reasoning="Complex or mixed tasks escalate to OMNIRA Prime orchestration.",
            )

        return RouteResponse(
            agent=best_rule.agent,
            model=best_rule.model,
            confidence=min(0.95, 0.6 + 0.1 * len(matched)),
            matched_keywords=matched,
            reasoning=best_rule.reasoning,
        )

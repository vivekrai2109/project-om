from __future__ import annotations

KEYWORDS = {
    "coder": ["bug", "fix", "refactor", "code", "implement", "function", "class"],
    "infra": ["deploy", "terraform", "docker", "k8s", "kubernetes", "aws", "azure", "gcp", "ci", "cd"],
    "docs": ["readme", "docs", "documentation", "guide", "manual"],
    "monitor": ["monitor", "alert", "metrics", "logging", "observability"],
    "planner": ["plan", "design", "architecture", "roadmap", "spec"],
    "qa": ["test", "unit", "integration", "e2e", "quality"],
    "security": ["security", "vuln", "secret", "compliance", "policy"],
    "release": ["release", "version", "changelog", "pipeline"],
    "research": ["research", "compare", "evaluate", "options"],
    "data": ["data", "analytics", "sql", "query", "dashboard"],
}


def pick_agent(task: str) -> str:
    text = task.lower()
    for agent, words in KEYWORDS.items():
        if any(w in text for w in words):
            return agent
    return "planner"

from __future__ import annotations

from dataclasses import dataclass


BLOCKED_KEYWORDS = (
    "ransomware",
    "credential theft",
    "data exfiltration",
    "malicious payload",
    "bypass detection",
)

APPROVAL_KEYWORDS = (
    "shell",
    "azure",
    "terraform apply",
    "kubectl apply",
    "delete",
    "trading",
)


@dataclass
class SafetyResult:
    allowed: bool
    risk_level: str
    flags: list[str]
    requires_approval: bool


class SafetyEngine:
    def classify_action_risk(self, text: str) -> str:
        lowered = text.lower()
        if any(keyword in lowered for keyword in BLOCKED_KEYWORDS):
            return "critical"
        if any(keyword in lowered for keyword in APPROVAL_KEYWORDS):
            return "high"
        if "security" in lowered or "scan" in lowered:
            return "medium"
        return "low"

    def evaluate(self, text: str, tools: list[str] | None = None) -> SafetyResult:
        lowered = text.lower()
        flags: list[str] = []
        if any(keyword in lowered for keyword in BLOCKED_KEYWORDS):
            flags.append("blocked-malicious-request")
            return SafetyResult(False, "critical", flags, False)

        if "offensive" in lowered and "defensive" not in lowered:
            flags.append("offensive-security-disallowed")
            return SafetyResult(False, "critical", flags, False)

        risk_level = self.classify_action_risk(text)
        requires_approval = bool(tools) or any(keyword in lowered for keyword in APPROVAL_KEYWORDS)
        if "security" in lowered:
            flags.append("defensive-security-only")
        return SafetyResult(True, risk_level, flags, requires_approval)

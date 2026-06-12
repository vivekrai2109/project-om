from __future__ import annotations

import re


OWNER_NAME = "Vivek"
OPERATING_LOOP = ("Understand", "Plan", "Risk Check", "Act", "Verify", "Respond", "Learn")

SUPPORTED_INTENTS: tuple[str, ...] = (
    "general_conversation",
    "voice_control",
    "backend_control",
    "open_operations",
    "hide_operations",
    "backend_status",
    "repo_analysis",
    "ui_improvement",
    "code_change",
    "self_improve_ui",
    "self_code_change",
    "debugging",
    "research",
    "memory_save",
    "memory_recall",
    "memory_control",
    "privacy_status",
    "learning_readiness",
    "tool_execution",
    "approval_response",
    "resource_status",
    "model_status",
)

LOCAL_COMMAND_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("voice_control", re.compile(r"\b(mute mic|unmute mic|mute microphone|unmute microphone)\b", re.IGNORECASE)),
    ("voice_control", re.compile(r"\b(mute voice|unmute voice|mute speaker|unmute speaker)\b", re.IGNORECASE)),
    ("voice_control", re.compile(r"^(start|resume|pause|stop|kill)(\s+jarvis)?$", re.IGNORECASE)),
    ("voice_control", re.compile(r"^(jarvis\s+)?(start|resume|pause|stop|kill)$", re.IGNORECASE)),
    ("voice_control", re.compile(r"^(jarvis\s+status|status\s+jarvis|control\s+status)$", re.IGNORECASE)),
    ("backend_control", re.compile(r"^(start|stop|restart)\s+omnira(\s+(backend|api|server))?$", re.IGNORECASE)),
    ("backend_control", re.compile(r"^omnira(\s+backend)?\s+status$", re.IGNORECASE)),
    ("open_operations", re.compile(r"\b(open|show) operations\b", re.IGNORECASE)),
    ("hide_operations", re.compile(r"\b(hide|close) operations\b", re.IGNORECASE)),
    ("backend_status", re.compile(r"\b(show )?(backend|omnira) status\b", re.IGNORECASE)),
    ("resource_status", re.compile(r"\b(resource|system) status\b", re.IGNORECASE)),
    ("model_status", re.compile(r"\b(model status|routing status)\b", re.IGNORECASE)),
    ("learning_readiness", re.compile(r"^(learning readiness|training readiness|readiness status)$", re.IGNORECASE)),
    ("privacy_status", re.compile(r"^(privacy status|learning status|memory status)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(don't remember this|do not remember this|dont remember this|forget this)\b", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(stop remembering|stop remembering things|disable memory|memory off)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(start remembering|enable memory|memory on)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(stop training on my data|disable training on my data|training off)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(start training on my data|enable training on my data|training on)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(stop recording what i do|disable observation|observation off)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(start recording what i do|enable observation|observation on)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(enable internet learning|internet learning on|disable internet learning|internet learning off)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(stop learning my profile|disable profile learning|profile learning off|start learning my profile|enable profile learning|profile learning on)$", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(set compute mode to|compute mode|use .+ compute mode)\b", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(set internet learning domains to|allow internet learning for|add internet learning domain|add internet learning domains|remove internet learning domain|remove internet learning domains)\b", re.IGNORECASE)),
    ("memory_control", re.compile(r"^(pin model to|use only model|unpin model|clear pinned model)\b", re.IGNORECASE)),
)

MEMORY_SAVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(remember this|save this as rule|prefer this style)\b", re.IGNORECASE),
)

MEMORY_RECALL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(remember|recall|what do you know about)\b", re.IGNORECASE),
)

APPROVAL_RESPONSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(approve|approved|reject|rejected|deny)\b", re.IGNORECASE),
)

RESEARCH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(research|compare|investigate|look up|evaluate)\b", re.IGNORECASE),
)

CODE_CHANGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(code change|fix|implement|refactor|patch|modify backend|modify code)\b", re.IGNORECASE),
)

SELF_CODE_CHANGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(self[- ]?code|recode yourself|improve yourself|build yourself|rewrite yourself)\b", re.IGNORECASE),
)

SELF_UI_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(improve ui|self[- ]?improve ui|redesign ui|polish presence mode)\b", re.IGNORECASE),
)

REPO_ANALYSIS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(repo analysis|inspect repo|analyze repo|scan repo|architecture summary)\b", re.IGNORECASE),
)

DEBUGGING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(debug|diagnose|why is|error|bug)\b", re.IGNORECASE),
)

RISK_BY_INTENT = {
    "general_conversation": "low",
    "voice_control": "low",
    "backend_control": "low",
    "open_operations": "low",
    "hide_operations": "low",
    "backend_status": "low",
    "resource_status": "low",
    "model_status": "low",
    "memory_save": "medium",
    "memory_recall": "low",
    "memory_control": "medium",
    "privacy_status": "low",
    "approval_response": "medium",
    "research": "low",
    "repo_analysis": "medium",
    "ui_improvement": "medium",
    "self_improve_ui": "high",
    "code_change": "high",
    "self_code_change": "critical",
    "debugging": "medium",
    "tool_execution": "high",
}

APPROVAL_REQUIRED_RISKS = {"high", "critical"}

INTENT_AGENT_MAP = {
    "general_conversation": "commander",
    "voice_control": "voice_engineer",
    "backend_control": "omnira_bridge",
    "open_operations": "commander",
    "hide_operations": "commander",
    "backend_status": "omnira_bridge",
    "resource_status": "resource_manager",
    "model_status": "omnira_bridge",
    "repo_analysis": "repo_analyst",
    "ui_improvement": "ui_designer",
    "self_improve_ui": "ui_designer",
    "code_change": "backend_engineer",
    "self_code_change": "architect",
    "debugging": "reviewer",
    "research": "research",
    "memory_save": "memory",
    "memory_recall": "memory",
    "memory_control": "memory",
    "privacy_status": "memory",
    "tool_execution": "backend_engineer",
    "approval_response": "security",
}

SPECIALIST_ROLE_SUMMARY = {
    "commander": "overall planning and orchestration",
    "architect": "system design, contracts, module boundaries",
    "ui_designer": "cinematic Jarvis UI and readability",
    "frontend_engineer": "QML and PySide implementation",
    "backend_engineer": "workflows, adapters, state, and events",
    "voice_engineer": "STT, TTS, wake word, interruption",
    "repo_analyst": "repo scanning and impact analysis",
    "reviewer": "code review and consistency",
    "test_engineer": "validation and smoke checks",
    "security": "risk, approval, and policy",
    "memory": "memory save, search, and preference handling",
    "research": "docs, comparisons, and technical research",
    "resource_manager": "resource health and routing efficiency",
    "omnira_bridge": "Jarvis to OMNIRA contract handling",
}

WHITELISTED_LOCAL_COMMANDS = {
    "mute mic",
    "unmute mic",
    "mute microphone",
    "unmute microphone",
    "mute voice",
    "unmute voice",
    "mute speaker",
    "unmute speaker",
    "start",
    "start jarvis",
    "pause",
    "pause jarvis",
    "stop",
    "stop jarvis",
    "resume",
    "resume jarvis",
    "kill",
    "kill jarvis",
    "jarvis status",
    "open operations",
    "hide operations",
    "show backend status",
    "enter debug mode",
    "exit debug mode",
}

SELF_CODE_WORKFLOW_STEPS: tuple[str, ...] = (
    "receive_owner_request",
    "classify_self_code_change",
    "scan_repo",
    "identify_impacted_files",
    "create_implementation_plan",
    "assess_risk",
    "generate_patch_proposal",
    "require_approval_before_apply",
    "prepare_validation_plan",
    "show_diff_summary",
    "capture_learning",
)

SELF_UI_WORKFLOW_STEPS: tuple[str, ...] = (
    "capture_ui_request",
    "summarize_current_ui_state",
    "analyze_ui_protocol",
    "propose_visual_changes",
    "identify_ui_files",
    "generate_patch_proposal",
    "require_approval_before_apply",
    "prepare_launch_and_compile_checks",
    "capture_before_after_notes",
    "save_design_preference_candidate",
)

UI_PROTOCOL_RULES: tuple[str, ...] = (
    "Presence Mode should be minimal by default",
    "operations hidden unless requested, error, approval, or debug",
    "text must remain readable",
    "central orb remains the visual focus",
    "bottom controls must be clear and concise",
    "status chips must stay compact and meaningful",
    "avoid clutter and debug-heavy placeholders",
    "cinematic but usable presentation",
)
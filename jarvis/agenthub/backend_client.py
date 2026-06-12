from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
import json
import time
from typing import Any, Iterable

import httpx

from .config import Config
from .memory_control import load_memory_control_state
from .models import get_model_for_agent


OPENAI_COMPATIBLE_BACKENDS = {"local", "omnira"}


OMNIRA_MODEL_MAP = {
    "coder": "omnira-code-qwen-coder-7b-v0.1",
    "infra": "omnira-platform-qwen-7b-v0.1",
    "monitor": "omnira-platform-qwen-7b-v0.1",
    "release": "omnira-platform-qwen-7b-v0.1",
    "planner": "omnira-reasoning-qwen-7b-v0.1",
    "docs": "omnira-research-qwen-14b-v0.1",
    "research": "omnira-research-qwen-14b-v0.1",
    "data": "omnira-research-qwen-14b-v0.1",
    "security": "omnira-shield-qwen-7b-v0.1",
    "qa": "omnira-code-qwen-coder-7b-v0.1",
}

OMNIRA_AGENT_MAP = {
    "assistant-lite": "omnira-lite",
    "coder": "omnira-code",
    "infra": "omnira-platform",
    "monitor": "omnira-platform",
    "release": "omnira-platform",
    "planner": "omnira-prime",
    "docs": "omnira-research",
    "research": "omnira-research",
    "data": "omnira-research",
    "security": "omnira-shield",
    "qa": "omnira-code",
}

OMNIRA_COMPUTE_MODEL_MAP: dict[str, dict[str, str]] = {
    "lean": {
        "planner": "omnira-lite-qwen-3b-v0.1",
        "docs": "omnira-lite-qwen-3b-v0.1",
        "research": "omnira-lite-qwen-3b-v0.1",
        "data": "omnira-lite-qwen-3b-v0.1",
        "coder": "omnira-code-qwen-coder-7b-v0.1",
        "qa": "omnira-code-qwen-coder-7b-v0.1",
        "security": "omnira-shield-qwen-7b-v0.1",
        "infra": "omnira-platform-qwen-7b-v0.1",
        "monitor": "omnira-platform-qwen-7b-v0.1",
        "release": "omnira-platform-qwen-7b-v0.1",
    },
    "balanced": dict(OMNIRA_MODEL_MAP),
    "performance": dict(OMNIRA_MODEL_MAP),
}

COMPUTE_MODE_REQUEST_PROFILE: dict[str, dict[str, object]] = {
    "lean": {"max_output_tokens": 384, "reasoning_effort": "low"},
    "balanced": {"max_output_tokens": 1024, "reasoning_effort": "medium"},
    "performance": {"max_output_tokens": 1536, "reasoning_effort": "high"},
}


def normalize_omnira_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _flatten_input_text(items: list[dict] | None) -> str:
    if not items:
        return ""
    parts: list[str] = []
    for item in items:
        for content in item.get("content", []):
            if content.get("type") in {"input_text", "text"}:
                text = content.get("text", "")
                if text:
                    parts.append(str(text))
    return "\n\n".join(parts).strip()


@dataclass
class OmniraModelItem:
    id: str


@dataclass
class OmniraModelsList:
    data: list[OmniraModelItem]


@dataclass
class OmniraResponseUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class JarvisOMNIRAResponse:
    reply_text: str = ""
    speech_text: str = ""
    state: str = "idle"
    intent: str = ""
    agent: str = ""
    model: str = ""
    provider: str = ""
    confidence: float = 0.0
    decision_path: list[str] = field(default_factory=list)
    memory_hits: list[dict[str, Any] | str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    workflow_trace: list[dict[str, Any]] = field(default_factory=list)
    visualization: dict[str, Any] = field(default_factory=dict)
    safety_flags: list[str] = field(default_factory=list)
    approval_required: bool = False
    risk_level: str = "low"
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OmniraResponse:
    output_text: str
    created_at: float
    usage: OmniraResponseUsage
    model: str = ""
    agent: str = ""
    provider: str = ""
    response: JarvisOMNIRAResponse = field(default_factory=JarvisOMNIRAResponse)


@dataclass
class OmniraStreamEvent:
    delta: str
    done: bool = False
    model: str = ""
    agent: str = ""
    provider: str = ""
    response: JarvisOMNIRAResponse = field(default_factory=JarvisOMNIRAResponse)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutingProfile:
    model_name: str | None
    max_output_tokens: int
    reasoning_effort: str
    compute_mode: str


def _normalize_memory_hits(value: object) -> list[dict[str, Any] | str]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any] | str] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append({str(key): item[key] for key in item})
        elif item is not None:
            normalized.append(str(item))
    return normalized


def _normalize_tool_calls(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append({str(key): item[key] for key in item})
        elif item is not None:
            normalized.append({"name": str(item), "status": "unknown"})
    return normalized


def _normalize_workflow_trace(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append({str(key): item[key] for key in item})
        elif item is not None:
            normalized.append({"step": str(item), "status": "ok", "detail": str(item)})
    return normalized


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item).strip()]


def normalize_omnira_response_payload(
    payload: dict[str, Any] | None,
    *,
    fallback_reply_text: str = "",
    fallback_model: str = "",
    fallback_agent: str = "",
    fallback_provider: str = "",
) -> JarvisOMNIRAResponse:
    raw = payload or {}
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    reply_text = str(
        raw.get("reply_text")
        or raw.get("response")
        or metadata.get("reply_text")
        or fallback_reply_text
        or ""
    ).strip()
    speech_text = str(raw.get("speech_text") or metadata.get("speech_text") or reply_text).strip()
    state = str(raw.get("state") or metadata.get("state") or ("approval_required" if raw.get("approval_required") else "speaking" if reply_text else "idle")).strip()
    return JarvisOMNIRAResponse(
        reply_text=reply_text,
        speech_text=speech_text,
        state=state or "idle",
        intent=str(raw.get("intent") or metadata.get("intent") or "").strip(),
        agent=str(raw.get("agent") or metadata.get("agent") or fallback_agent or "").strip(),
        model=str(raw.get("model") or metadata.get("model") or fallback_model or "").strip(),
        provider=str(raw.get("provider") or metadata.get("provider") or fallback_provider or "").strip(),
        confidence=max(0.0, min(1.0, float(raw.get("confidence") or metadata.get("confidence") or 0.0))),
        decision_path=_normalize_string_list(raw.get("decision_path") or metadata.get("decision_path")),
        memory_hits=_normalize_memory_hits(raw.get("memory_hits") or metadata.get("memory_hits")),
        tool_calls=_normalize_tool_calls(raw.get("tool_calls") or metadata.get("tool_calls")),
        workflow_trace=_normalize_workflow_trace(raw.get("workflow_trace") or metadata.get("workflow_trace")),
        visualization=dict(raw.get("visualization") or metadata.get("visualization") or {}),
        safety_flags=_normalize_string_list(raw.get("safety_flags") or metadata.get("safety_flags")),
        approval_required=bool(raw.get("approval_required") if "approval_required" in raw else metadata.get("requires_approval") or metadata.get("approval_required") or False),
        risk_level=str(raw.get("risk_level") or metadata.get("risk_level") or "low").strip() or "low",
        error=(raw.get("error") if isinstance(raw.get("error"), dict) else metadata.get("error") if isinstance(metadata.get("error"), dict) else None),
        metadata=dict(metadata),
    )


class OmniraModelsAPI:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def list(self) -> OmniraModelsList:
        response = httpx.get(f"{normalize_omnira_base_url(self.cfg.base_url)}/models", timeout=10)
        response.raise_for_status()
        payload = response.json()
        return OmniraModelsList(data=[OmniraModelItem(id=str(item.get("id", ""))) for item in payload])


class OmniraResponsesAPI:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def create(
        self,
        model: str | None,
        input: list[dict],
        max_output_tokens: int,
        reasoning: dict[str, Any] | None = None,
        timeout: int = 120,
        stream: bool = False,
        preferred_agent: str | None = None,
    ) -> OmniraResponse | Iterable[OmniraStreamEvent]:
        system_prompt = ""
        user_text = ""
        if input:
            system_prompt = _flatten_input_text([input[0]]) if input[0].get("role") == "system" else ""
            user_items = [item for item in input if item.get("role") == "user"]
            user_text = _flatten_input_text(user_items)

        payload = {
            "message": user_text,
            "system_prompt": system_prompt or None,
            "metadata": {
                "source": "jarvis",
                "max_output_tokens": max_output_tokens,
                "reasoning": reasoning or {},
                "compute_mode": _current_compute_mode(),
                "pinned_model": _current_pinned_model(),
                "jarvis_contract_version": "1.0",
            },
        }
        if model:
            payload["preferred_model"] = model
        if preferred_agent:
            payload["preferred_agent"] = preferred_agent

        if stream:
            return self._stream_chat(payload, timeout=timeout)

        response = httpx.post(
            f"{normalize_omnira_base_url(self.cfg.base_url)}/chat",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        normalized = normalize_omnira_response_payload(
            payload,
            fallback_model=str(model or ""),
            fallback_agent=str(preferred_agent or ""),
        )
        text = normalized.reply_text
        usage = OmniraResponseUsage(
            input_tokens=max(1, len(user_text.split())),
            output_tokens=max(1, len(text.split())),
            total_tokens=max(2, len(user_text.split()) + len(text.split())),
        )
        if stream:
            return self._stream_text(text)
        return OmniraResponse(
            output_text=text,
            created_at=time.time(),
            usage=usage,
            model=normalized.model or str(model or ""),
            agent=normalized.agent or str(preferred_agent or ""),
            provider=normalized.provider,
            response=normalized,
        )

    def _stream_chat(self, payload: dict[str, Any], *, timeout: int) -> Iterable[OmniraStreamEvent]:
        reply_parts: list[str] = []
        with httpx.stream(
            "POST",
            f"{normalize_omnira_base_url(self.cfg.base_url)}/chat/stream",
            json=payload,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                item = json.loads(line)
                delta = str(item.get("delta") or "")
                if delta:
                    reply_parts.append(delta)
                normalized = normalize_omnira_response_payload(
                    item,
                    fallback_reply_text="".join(reply_parts),
                    fallback_model=str(item.get("model") or payload.get("preferred_model") or ""),
                    fallback_agent=str(item.get("agent") or payload.get("preferred_agent") or ""),
                    fallback_provider=str(item.get("provider") or ""),
                )
                yield OmniraStreamEvent(
                    delta=delta,
                    done=bool(item.get("done", False)),
                    model=normalized.model,
                    agent=normalized.agent,
                    provider=normalized.provider,
                    response=normalized,
                    metadata=dict(item.get("metadata") or {}),
                )
                if item.get("done"):
                    break

    def _stream_text(self, text: str) -> Iterable[OmniraStreamEvent]:
        if not text:
            return []
        chunks = [chunk + " " for chunk in text.split()]
        return [OmniraStreamEvent(delta=chunk) for chunk in chunks]


class OmniraClient:
    def __init__(self, cfg: Config) -> None:
        self.responses = OmniraResponsesAPI(cfg)
        self.models = OmniraModelsAPI(cfg)


def is_openai_compatible_backend(backend: str) -> bool:
    return backend in OPENAI_COMPATIBLE_BACKENDS


def _current_compute_mode() -> str:
    try:
        return load_memory_control_state().compute_mode
    except Exception:
        return "balanced"


def _current_pinned_model() -> str:
    try:
        return str(load_memory_control_state().pinned_model or "").strip()
    except Exception:
        return ""


def build_routing_profile(
    agent_name: str,
    agent_model: str | None,
    cfg: Config,
    dynamic_routing: bool = False,
    compute_mode: str | None = None,
) -> RoutingProfile:
    effective_compute_mode = str(compute_mode or _current_compute_mode() or "balanced").strip().lower() or "balanced"
    pinned_model = _current_pinned_model()
    request_profile = COMPUTE_MODE_REQUEST_PROFILE.get(effective_compute_mode, COMPUTE_MODE_REQUEST_PROFILE["balanced"])
    if agent_model:
        return RoutingProfile(
            model_name=agent_model,
            max_output_tokens=int(request_profile["max_output_tokens"]),
            reasoning_effort=str(request_profile["reasoning_effort"]),
            compute_mode=effective_compute_mode,
        )
    if pinned_model:
        return RoutingProfile(
            model_name=pinned_model,
            max_output_tokens=int(request_profile["max_output_tokens"]),
            reasoning_effort=str(request_profile["reasoning_effort"]),
            compute_mode=effective_compute_mode,
        )
    if cfg.backend == "omnira":
        if dynamic_routing:
            return RoutingProfile(
                model_name=None,
                max_output_tokens=int(request_profile["max_output_tokens"]),
                reasoning_effort=str(request_profile["reasoning_effort"]),
                compute_mode=effective_compute_mode,
            )
        model_map = OMNIRA_COMPUTE_MODEL_MAP.get(effective_compute_mode, OMNIRA_MODEL_MAP)
        return RoutingProfile(
            model_name=model_map.get(agent_name, "omnira-lite-qwen-3b-v0.1"),
            max_output_tokens=int(request_profile["max_output_tokens"]),
            reasoning_effort=str(request_profile["reasoning_effort"]),
            compute_mode=effective_compute_mode,
        )
    if is_openai_compatible_backend(cfg.backend):
        return RoutingProfile(
            model_name=get_model_for_agent(agent_name, cfg.model),
            max_output_tokens=min(int(cfg.max_output_tokens), int(request_profile["max_output_tokens"])),
            reasoning_effort=str(request_profile["reasoning_effort"]),
            compute_mode=effective_compute_mode,
        )
    return RoutingProfile(
        model_name=cfg.model,
        max_output_tokens=min(int(cfg.max_output_tokens), int(request_profile["max_output_tokens"])),
        reasoning_effort=str(request_profile["reasoning_effort"]),
        compute_mode=effective_compute_mode,
    )


def resolve_model_name(agent_name: str, agent_model: str | None, cfg: Config, dynamic_routing: bool = False) -> str | None:
    return build_routing_profile(agent_name, agent_model, cfg, dynamic_routing=dynamic_routing).model_name


def resolve_omnira_agent_name(agent_name: str, dynamic_routing: bool = False) -> str | None:
    if dynamic_routing:
        return None
    return OMNIRA_AGENT_MAP.get(agent_name)


def normalize_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return base


def create_openai_client(cfg: Config):
    from openai import OpenAI

    api_key = os.environ.get(cfg.api_key_env, "")
    if cfg.backend == "omnira":
        return OmniraClient(cfg)
    if is_openai_compatible_backend(cfg.backend):
        return OpenAI(base_url=normalize_base_url(cfg.base_url), api_key=api_key or "local")
    return OpenAI(api_key=api_key or None)


def check_backend_connection(cfg: Config) -> tuple[bool, str]:
    api_key = os.environ.get(cfg.api_key_env, "")

    if cfg.backend == "omnira":
        if not cfg.base_url:
            return False, "base_url is not set in config.yaml for backend 'omnira'"
        url = normalize_omnira_base_url(cfg.base_url) + "/models"
        try:
            resp = httpx.get(url, timeout=10)
            ok = resp.status_code == 200
            return ok, f"GET {url} -> {resp.status_code}"
        except Exception as exc:
            return False, f"error: {exc}"

    if is_openai_compatible_backend(cfg.backend):
        if not cfg.base_url:
            return False, f"base_url is not set in config.yaml for backend '{cfg.backend}'"
        url = normalize_base_url(cfg.base_url) + "/models"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = httpx.get(url, headers=headers, timeout=10)
            ok = resp.status_code == 200
            return ok, f"GET {url} -> {resp.status_code}"
        except Exception as exc:
            return False, f"error: {exc}"

    if not api_key:
        return False, f"{cfg.api_key_env} not set"

    try:
        client = create_openai_client(cfg)
        models = client.models.list()
        count = len(getattr(models, "data", []))
        return True, f"OpenAI models available: {count}"
    except ModuleNotFoundError as exc:
        if exc.name == "openai":
            return False, "openai package is not installed. Activate the project virtual environment and run 'pip install -e .'."
        return False, f"missing dependency: {exc.name}"
    except Exception as exc:
        return False, f"error: {exc}"
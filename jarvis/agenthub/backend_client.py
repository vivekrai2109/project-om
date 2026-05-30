from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Iterable

import httpx

from .config import Config
from .models import get_model_for_agent


OPENAI_COMPATIBLE_BACKENDS = {"local", "omnira"}


OMNIRA_MODEL_MAP = {
    "coder": "omnira-code-qwen-coder-7b-v0.1",
    "infra": "omnira-platform-qwen-7b-v0.1",
    "monitor": "omnira-platform-qwen-7b-v0.1",
    "release": "omnira-platform-qwen-7b-v0.1",
    "planner": "omnira-prime-qwen-platform-routing",
    "docs": "omnira-research-qwen-14b-v0.1",
    "research": "omnira-research-qwen-14b-v0.1",
    "data": "omnira-research-qwen-14b-v0.1",
    "security": "omnira-shield-qwen-7b-v0.1",
    "qa": "omnira-code-qwen-coder-7b-v0.1",
}

OMNIRA_AGENT_MAP = {
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
class OmniraResponse:
    output_text: str
    created_at: float
    usage: OmniraResponseUsage
    model: str = ""
    agent: str = ""


@dataclass
class OmniraStreamEvent:
    delta: str


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
            },
        }
        if model:
            payload["preferred_model"] = model
        if preferred_agent:
            payload["preferred_agent"] = preferred_agent

        response = httpx.post(
            f"{normalize_omnira_base_url(self.cfg.base_url)}/chat",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        text = str(payload.get("response", ""))
        usage = OmniraResponseUsage(
            input_tokens=max(1, len(user_text.split())),
            output_tokens=max(1, len(text.split())),
            total_tokens=max(2, len(user_text.split()) + len(text.split())),
        )
        if stream:
            return self._stream_text(text)
        return OmniraResponse(
            output_text=text,
            created_at=0.0,
            usage=usage,
            model=str(payload.get("model") or model or ""),
            agent=str(payload.get("agent") or preferred_agent or ""),
        )

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


def resolve_model_name(agent_name: str, agent_model: str | None, cfg: Config, dynamic_routing: bool = False) -> str | None:
    if agent_model:
        return agent_model
    if cfg.backend == "omnira":
        if dynamic_routing:
            return None
        return OMNIRA_MODEL_MAP.get(agent_name, "omnira-lite-qwen-3b-v0.1")
    if is_openai_compatible_backend(cfg.backend):
        return get_model_for_agent(agent_name, cfg.model)
    return cfg.model


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
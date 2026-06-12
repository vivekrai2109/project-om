from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.schemas import ModelRequest, ModelResponse, ModelStreamEvent


class BaseModelProvider(ABC):
    provider_name: str

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    @abstractmethod
    def stream_generate(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class ProviderUnavailableError(RuntimeError):
    """Raised when a model provider cannot currently serve a request."""


@dataclass(frozen=True)
class OllamaProfile:
    model: str
    max_tokens: int
    num_ctx: int
    profile: str


class MockProvider(BaseModelProvider):
    provider_name = "mock"

    def generate(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        prompt = request.prompt or (request.messages[-1].content if request.messages else "")
        content = (
            f"OMNIRA mock response for '{prompt[:120]}' using {request.model or 'default'}"
        )
        latency_ms = int((perf_counter() - started) * 1000)
        return ModelResponse(
            content=content,
            model_used=request.model or "mock-default",
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=max(1, len(prompt.split())),
            tokens_out=max(8, len(content.split())),
            metadata={"mode": "mock"},
        )

    def stream_generate(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        prompt = request.prompt or (request.messages[-1].content if request.messages else "")
        content = f"OMNIRA mock response for '{prompt[:120]}' using {request.model or 'default'}"
        for chunk in content.split():
            yield ModelStreamEvent(delta=chunk + " ", model_used=request.model or "mock-default", provider=self.provider_name)
        yield ModelStreamEvent(done=True, model_used=request.model or "mock-default", provider=self.provider_name, metadata={"mode": "mock"})


class OllamaProvider(BaseModelProvider):
    provider_name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _resolve_profile(self, requested_model: str | None, requested_max_tokens: int) -> OllamaProfile:
        if requested_model and ":" in requested_model:
            return OllamaProfile(
                model=requested_model,
                max_tokens=max(1, requested_max_tokens),
                num_ctx=self.settings.ollama_default_num_ctx,
                profile="direct",
            )

        model_map = {
            "omnira-lite-qwen-3b-v0.1": OllamaProfile(
                model=self.settings.ollama_fast_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_fast_max_tokens),
                num_ctx=self.settings.ollama_fast_num_ctx,
                profile="fast",
            ),
            "omnira-bharat-qwen-7b-v0.1": OllamaProfile(
                model=self.settings.ollama_fast_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_fast_max_tokens),
                num_ctx=self.settings.ollama_fast_num_ctx,
                profile="fast",
            ),
            "omnira-coach-qwen-7b-v0.1": OllamaProfile(
                model=self.settings.ollama_fast_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_fast_max_tokens),
                num_ctx=self.settings.ollama_fast_num_ctx,
                profile="fast",
            ),
            "omnira-code-qwen-coder-7b-v0.1": OllamaProfile(
                model=self.settings.ollama_code_model or self.settings.ollama_default_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_default_max_tokens),
                num_ctx=self.settings.ollama_default_num_ctx,
                profile="code",
            ),
            "omnira-platform-qwen-7b-v0.1": OllamaProfile(
                model=self.settings.ollama_platform_model or self.settings.ollama_default_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_default_max_tokens),
                num_ctx=self.settings.ollama_default_num_ctx,
                profile="platform",
            ),
            "omnira-reasoning-qwen-7b-v0.1": OllamaProfile(
                model=self.settings.ollama_reasoning_model or self.settings.ollama_platform_model or self.settings.ollama_default_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_reasoning_max_tokens),
                num_ctx=self.settings.ollama_reasoning_num_ctx,
                profile="reasoning",
            ),
            "omnira-shield-qwen-7b-v0.1": OllamaProfile(
                model=self.settings.ollama_platform_model or self.settings.ollama_default_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_default_max_tokens),
                num_ctx=self.settings.ollama_default_num_ctx,
                profile="platform",
            ),
            "omnira-trade-qwen-7b-v0.1": OllamaProfile(
                model=self.settings.ollama_platform_model or self.settings.ollama_default_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_default_max_tokens),
                num_ctx=self.settings.ollama_default_num_ctx,
                profile="platform",
            ),
            "omnira-research-qwen-14b-v0.1": OllamaProfile(
                model=self.settings.ollama_research_model or self.settings.ollama_default_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_research_max_tokens),
                num_ctx=self.settings.ollama_default_num_ctx,
                profile="research",
            ),
        }
        return model_map.get(
            requested_model or "",
            OllamaProfile(
                model=self.settings.ollama_default_model,
                max_tokens=min(requested_max_tokens, self.settings.ollama_default_max_tokens),
                num_ctx=self.settings.ollama_default_num_ctx,
                profile="default",
            ),
        )

    def _apply_compute_mode(self, profile: OllamaProfile, metadata: dict[str, object]) -> OllamaProfile:
        compute_mode = str(metadata.get("compute_mode") or "balanced").strip().lower() or "balanced"
        if compute_mode == "lean":
            return OllamaProfile(
                model=profile.model,
                max_tokens=max(64, min(profile.max_tokens, self.settings.ollama_fast_max_tokens)),
                num_ctx=max(1024, min(profile.num_ctx, self.settings.ollama_fast_num_ctx)),
                profile=f"{profile.profile}-lean",
            )
        if compute_mode == "performance":
            return OllamaProfile(
                model=profile.model,
                max_tokens=max(profile.max_tokens, min(self.settings.ollama_reasoning_max_tokens, profile.max_tokens * 2)),
                num_ctx=max(profile.num_ctx, self.settings.ollama_reasoning_num_ctx),
                profile=f"{profile.profile}-performance",
            )
        return profile

    def _build_messages(self, request: ModelRequest) -> list[dict[str, str]]:
        messages = [message.model_dump() for message in request.messages]
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        if not messages:
            messages.append({"role": "user", "content": ""})
        return messages

    def _post_chat(self, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            url=f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.settings.ollama_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _stream_chat(self, payload: dict[str, object]) -> Iterator[dict[str, object]]:
        request = Request(
            url=f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.settings.ollama_timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                yield json.loads(line)

    def generate(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        profile = self._apply_compute_mode(self._resolve_profile(request.model, request.max_tokens), request.metadata)
        payload = {
            "model": profile.model,
            "messages": self._build_messages(request),
            "stream": False,
            "keep_alive": self.settings.ollama_keep_alive,
            "options": {
                "temperature": request.temperature,
                "num_predict": profile.max_tokens,
                "num_ctx": profile.num_ctx,
            },
        }
        try:
            response_payload = self._post_chat(payload)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ProviderUnavailableError(f"Ollama request failed: {error}") from error

        message = response_payload.get("message") or {}
        content = str(message.get("content", "")).strip()
        latency_ms = int((perf_counter() - started) * 1000)
        return ModelResponse(
            content=content or "Ollama returned an empty response.",
            model_used=request.model or self.settings.default_model,
            provider=self.provider_name,
            latency_ms=latency_ms,
            tokens_in=int(response_payload.get("prompt_eval_count") or 0),
            tokens_out=int(response_payload.get("eval_count") or 0),
            metadata={
                "ollama_model": profile.model,
                "ollama_profile": profile.profile,
                "keep_alive": self.settings.ollama_keep_alive,
                "done": bool(response_payload.get("done", False)),
            },
        )

    def stream_generate(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        profile = self._apply_compute_mode(self._resolve_profile(request.model, request.max_tokens), request.metadata)
        payload = {
            "model": profile.model,
            "messages": self._build_messages(request),
            "stream": True,
            "keep_alive": self.settings.ollama_keep_alive,
            "options": {
                "temperature": request.temperature,
                "num_predict": profile.max_tokens,
                "num_ctx": profile.num_ctx,
            },
        }
        try:
            for response_payload in self._stream_chat(payload):
                message = response_payload.get("message") or {}
                content = str(message.get("content", ""))
                done = bool(response_payload.get("done", False))
                if content:
                    yield ModelStreamEvent(
                        delta=content,
                        done=False,
                        model_used=request.model or self.settings.default_model,
                        provider=self.provider_name,
                        metadata={
                            "ollama_model": profile.model,
                            "ollama_profile": profile.profile,
                        },
                    )
                if done:
                    yield ModelStreamEvent(
                        done=True,
                        model_used=request.model or self.settings.default_model,
                        provider=self.provider_name,
                        metadata={
                            "ollama_model": profile.model,
                            "ollama_profile": profile.profile,
                            "keep_alive": self.settings.ollama_keep_alive,
                            "prompt_eval_count": int(response_payload.get("prompt_eval_count") or 0),
                            "eval_count": int(response_payload.get("eval_count") or 0),
                        },
                    )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ProviderUnavailableError(f"Ollama request failed: {error}") from error


class VLLMProvider(BaseModelProvider):
    provider_name = "vllm"

    def generate(self, request: ModelRequest) -> ModelResponse:
        # TODO: add vLLM OpenAI-compatible integration for self-hosted models.
        raise NotImplementedError("vLLM provider is a future placeholder.")

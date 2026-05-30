from __future__ import annotations

from app.config import get_settings
from app.models.providers import (
    BaseModelProvider,
    MockProvider,
    OllamaProvider,
    ProviderUnavailableError,
)
from app.schemas import ModelRequest, ModelResponse


MODEL_CATALOG: tuple[dict[str, str], ...] = (
    {
        "id": "omnira-lite-qwen-3b-v0.1",
        "family": "OMNIRA Lite",
        "role": "personal-assistant",
        "description": "Fast personal assistant for daily and general tasks.",
    },
    {
        "id": "omnira-code-qwen-coder-7b-v0.1",
        "family": "OMNIRA Code",
        "role": "coding",
        "description": "Software engineering, repo, and debugging specialist.",
    },
    {
        "id": "omnira-platform-qwen-7b-v0.1",
        "family": "OMNIRA Platform",
        "role": "platform",
        "description": "Platform, cloud, DevOps, and infrastructure specialist.",
    },
    {
        "id": "omnira-bharat-qwen-7b-v0.1",
        "family": "OMNIRA Bharat",
        "role": "india-language",
        "description": "Hindi, Hinglish, and India-context assistant.",
    },
    {
        "id": "omnira-coach-qwen-7b-v0.1",
        "family": "OMNIRA Coach",
        "role": "coaching",
        "description": "Learning, career, and habit coaching assistant.",
    },
    {
        "id": "omnira-research-qwen-14b-v0.1",
        "family": "OMNIRA Research",
        "role": "research",
        "description": "Document-heavy analysis and deep research specialist.",
    },
    {
        "id": "omnira-shield-qwen-7b-v0.1",
        "family": "OMNIRA Shield",
        "role": "security",
        "description": "Defensive security and safety-bounded specialist.",
    },
    {
        "id": "omnira-trade-qwen-7b-v0.1",
        "family": "OMNIRA Trade",
        "role": "trading-research",
        "description": "Trading research and strategy specialist.",
    },
)


class ModelService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.providers: dict[str, BaseModelProvider] = {
            "mock": MockProvider(),
            "ollama": OllamaProvider(settings),
        }
        self.default_provider = "mock"
        if settings.enable_ollama or settings.enable_external_providers:
            self.default_provider = "ollama"

    def list_models(self) -> list[dict[str, str]]:
        return [
            {
                **entry,
                "provider": self.default_provider,
            }
            for entry in MODEL_CATALOG
        ]

    def generate(self, request: ModelRequest, provider_name: str | None = None) -> ModelResponse:
        selected_provider = provider_name or self.default_provider
        provider = self.providers[selected_provider]
        try:
            return provider.generate(request)
        except ProviderUnavailableError as error:
            fallback = self.providers["mock"].generate(request)
            fallback.metadata["fallback_reason"] = str(error)
            fallback.metadata["requested_provider"] = selected_provider
            fallback.safety_flags.append("provider-fallback")
            return fallback

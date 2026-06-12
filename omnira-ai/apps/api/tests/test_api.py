from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models.providers import OllamaProvider
from app.models.service import ModelService
from app.schemas import ModelRequest


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_route_endpoint_prefers_platform_for_azure_text() -> None:
    response = client.post("/models/route", json={"message": "Help with Azure Terraform deployment"})
    assert response.status_code == 200
    assert response.json()["agent"] in {"omnira-platform", "omnira-prime"}


def test_route_endpoint_uses_reasoning_model_for_complex_planning() -> None:
    response = client.post(
        "/models/route",
        json={"message": "Plan and orchestrate a complex repo migration and compare rollout options"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "omnira-prime"
    assert payload["model"] == "omnira-reasoning-qwen-7b-v0.1"


def test_route_endpoint_honors_pinned_model_metadata() -> None:
    response = client.post(
        "/models/route",
        json={
            "message": "Plan and orchestrate a complex repo migration and compare rollout options",
            "metadata": {"pinned_model": "omnira-platform-qwen-7b-v0.1"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "omnira-platform-qwen-7b-v0.1"
    assert payload["agent"] == "omnira-platform"


def test_chat_endpoint_returns_metadata() -> None:
    response = client.post("/chat", json={"message": "Summarize my repo health"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["response"]
    assert payload["agent"]
    assert payload["model"]


def test_chat_endpoint_honors_lean_compute_mode_metadata() -> None:
    response = client.post(
        "/chat",
        json={
            "message": "Research and analyze this repo architecture",
            "metadata": {"source": "jarvis", "compute_mode": "lean"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "omnira-lite-qwen-3b-v0.1"


def test_chat_endpoint_allows_preferred_model_and_agent() -> None:
    response = client.post(
        "/chat",
        json={
            "message": "Give me a platform summary",
            "preferred_agent": "omnira-platform",
            "preferred_model": "omnira-platform-qwen-7b-v0.1",
            "system_prompt": "You are a platform assistant.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "omnira-platform"
    assert payload["model"] == "omnira-platform-qwen-7b-v0.1"


def test_chat_endpoint_allows_preferred_agent_without_model() -> None:
    response = client.post(
        "/chat",
        json={
            "message": "Help me prepare for interviews",
            "preferred_agent": "omnira-coach",
            "metadata": {"source": "jarvis"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "omnira-coach"
    assert payload["model"] == "omnira-coach-qwen-7b-v0.1"


def test_chat_endpoint_routes_personal_tasks_to_lite() -> None:
    response = client.post(
        "/chat",
        json={
            "message": "Remind me to organize my calendar for tomorrow",
            "metadata": {"source": "jarvis"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "omnira-lite"
    assert payload["model"] == "omnira-lite-qwen-3b-v0.1"


def test_models_endpoint_exposes_full_catalog() -> None:
    response = client.get("/models")
    assert response.status_code == 200
    payload = response.json()
    model_ids = {item["id"] for item in payload}
    assert "omnira-lite-qwen-3b-v0.1" in model_ids
    assert "omnira-code-qwen-coder-7b-v0.1" in model_ids
    assert "omnira-reasoning-qwen-7b-v0.1" in model_ids
    assert "omnira-research-qwen-14b-v0.1" in model_ids
    lite_entry = next(item for item in payload if item["id"] == "omnira-lite-qwen-3b-v0.1")
    assert lite_entry["role"] == "personal-assistant"


def test_model_service_uses_mock_by_default(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_OLLAMA", "false")
    monkeypatch.setenv("ENABLE_EXTERNAL_PROVIDERS", "false")
    get_settings.cache_clear()
    service = ModelService()
    assert service.default_provider == "mock"
    monkeypatch.delenv("ENABLE_OLLAMA", raising=False)
    monkeypatch.delenv("ENABLE_EXTERNAL_PROVIDERS", raising=False)
    get_settings.cache_clear()


def test_model_service_ollama_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_OLLAMA", "true")
    get_settings.cache_clear()

    service = ModelService()

    def raise_unavailable(_request):
        from app.models.providers import ProviderUnavailableError

        raise ProviderUnavailableError("ollama offline")

    monkeypatch.setattr(service.providers["ollama"], "generate", raise_unavailable)
    response = service.generate(ModelRequest(prompt="Use platform routing", model="omnira-platform-qwen-7b-v0.1"))

    assert response.provider == "mock"
    assert response.metadata["requested_provider"] == "ollama"
    assert "provider-fallback" in response.safety_flags
    monkeypatch.delenv("ENABLE_OLLAMA", raising=False)
    get_settings.cache_clear()


def test_ollama_provider_parses_response(monkeypatch) -> None:
    get_settings.cache_clear()
    provider = OllamaProvider(get_settings())

    def fake_post_chat(_payload):
        return {
            "message": {"content": "OMNIRA local Ollama response"},
            "prompt_eval_count": 12,
            "eval_count": 18,
            "done": True,
        }

    monkeypatch.setattr(provider, "_post_chat", fake_post_chat)
    response = provider.generate(ModelRequest(prompt="hello", model="omnira-platform-qwen-7b-v0.1"))

    assert response.provider == "ollama"
    assert response.content == "OMNIRA local Ollama response"
    assert response.metadata["ollama_model"]


def test_ollama_provider_uses_fast_profile_for_lite(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_FAST_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("OLLAMA_FAST_MAX_TOKENS", "192")
    monkeypatch.setenv("OLLAMA_FAST_NUM_CTX", "1536")
    get_settings.cache_clear()
    provider = OllamaProvider(get_settings())
    captured: dict[str, object] = {}

    def fake_post_chat(payload):
        captured.update(payload)
        return {
            "message": {"content": "fast response"},
            "prompt_eval_count": 10,
            "eval_count": 12,
            "done": True,
        }

    monkeypatch.setattr(provider, "_post_chat", fake_post_chat)
    response = provider.generate(ModelRequest(prompt="hello", model="omnira-lite-qwen-3b-v0.1", max_tokens=512))

    assert captured["model"] == "qwen2.5:3b"
    assert captured["keep_alive"] == provider.settings.ollama_keep_alive
    assert captured["options"]["num_predict"] == 192
    assert captured["options"]["num_ctx"] == 1536
    assert response.metadata["ollama_profile"] == "fast"
    monkeypatch.delenv("OLLAMA_FAST_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_FAST_MAX_TOKENS", raising=False)
    monkeypatch.delenv("OLLAMA_FAST_NUM_CTX", raising=False)
    get_settings.cache_clear()


def test_ollama_provider_uses_reasoning_profile(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_REASONING_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("OLLAMA_REASONING_MAX_TOKENS", "900")
    monkeypatch.setenv("OLLAMA_REASONING_NUM_CTX", "6144")
    get_settings.cache_clear()
    provider = OllamaProvider(get_settings())
    captured: dict[str, object] = {}

    def fake_post_chat(payload):
        captured.update(payload)
        return {
            "message": {"content": "reasoning response"},
            "prompt_eval_count": 14,
            "eval_count": 20,
            "done": True,
        }

    monkeypatch.setattr(provider, "_post_chat", fake_post_chat)
    response = provider.generate(ModelRequest(prompt="plan a migration", model="omnira-reasoning-qwen-7b-v0.1", max_tokens=5000))

    assert captured["model"] == "qwen2.5:7b"
    assert captured["options"]["num_predict"] == 900
    assert captured["options"]["num_ctx"] == 6144
    assert response.metadata["ollama_profile"] == "reasoning"
    monkeypatch.delenv("OLLAMA_REASONING_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_REASONING_MAX_TOKENS", raising=False)
    monkeypatch.delenv("OLLAMA_REASONING_NUM_CTX", raising=False)
    get_settings.cache_clear()


def test_memory_and_rag_endpoints() -> None:
    save_response = client.post(
        "/memory/save",
        json={
            "record": {
                "type": "project",
                "title": "OMNIRA planning",
                "content": "Need a platform model and memory system.",
                "tags": ["plan"],
                "source": "test",
                "importance": 3,
                "metadata": {},
            }
        },
    )
    assert save_response.status_code == 200

    search_response = client.get("/memory/search", params={"query": "platform"})
    assert search_response.status_code == 200
    assert search_response.json()["results"]

    ingest_response = client.post(
        "/rag/ingest",
        json={"title": "Architecture", "content": "OMNIRA Prime orchestrates routing and memory."},
    )
    assert ingest_response.status_code == 200

    query_response = client.post("/rag/query", json={"query": "What orchestrates memory?"})
    assert query_response.status_code == 200
    assert query_response.json()["answer"]

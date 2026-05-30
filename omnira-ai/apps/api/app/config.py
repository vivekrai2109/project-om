from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


API_BASE_DIR = Path(__file__).resolve().parents[1]
API_ENV_FILE = API_BASE_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "OMNIRA Core API"
    environment: str = "development"
    api_port: int = 8000
    default_model: str = "omnira-lite-qwen-3b-v0.1"
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 300.0
    enable_ollama: bool = False
    ollama_default_model: str = "qwen2.5:7b"
    ollama_fast_model: str = "qwen2.5:3b"
    ollama_code_model: str | None = None
    ollama_platform_model: str | None = None
    ollama_research_model: str | None = None
    ollama_keep_alive: str = "20m"
    ollama_default_num_ctx: int = 4096
    ollama_fast_num_ctx: int = 2048
    ollama_default_max_tokens: int = 512
    ollama_fast_max_tokens: int = 256
    ollama_research_max_tokens: int = 768
    data_dir: Path = Path(".data")
    memory_file: Path = Path(".data/memory.json")
    enable_external_providers: bool = False
    enable_tool_execution: bool = False
    require_approval_for_tools: bool = True

    model_config = SettingsConfigDict(
        env_file=str(API_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.memory_file.parent.mkdir(parents=True, exist_ok=True)
    return settings

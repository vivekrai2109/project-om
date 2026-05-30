from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ModelRequest(BaseModel):
    prompt: str = ""
    system_prompt: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 512
    tools_allowed: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    content: str
    model_used: str
    provider: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    safety_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteRequest(BaseModel):
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteResponse(BaseModel):
    agent: str
    model: str
    confidence: float
    matched_keywords: list[str] = Field(default_factory=list)
    reasoning: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    system_prompt: str | None = None
    preferred_model: str | None = None
    preferred_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str
    model: str
    agent: str
    provider: str
    decision_path: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    importance: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemorySaveRequest(BaseModel):
    record: MemoryRecord


class MemorySearchResponse(BaseModel):
    query: str
    results: list[MemoryRecord]


class RagIngestRequest(BaseModel):
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagQueryRequest(BaseModel):
    query: str
    top_k: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagQueryResponse(BaseModel):
    answer: str
    matches: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    agent: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    agent: str
    result: str
    model: str
    provider: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str

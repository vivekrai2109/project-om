from fastapi import FastAPI, Query

from app.agents.service import AgentService
from app.chat.orchestrator import OmniraPrimeOrchestrator
from app.health import get_health
from app.memory.service import MemoryService
from app.models.router import ModelRouter
from app.models.service import ModelService
from app.rag.service import RagService
from app.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MemorySaveRequest,
    MemorySearchResponse,
    RagIngestRequest,
    RagIngestResponse,
    RagQueryRequest,
    RagQueryResponse,
    RouteRequest,
    RouteResponse,
)

app = FastAPI(title="OMNIRA Core API", version="0.1.0")

model_service = ModelService()
model_router = ModelRouter()
memory_service = MemoryService()
rag_service = RagService()
agent_service = AgentService()
prime = OmniraPrimeOrchestrator()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return get_health()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return prime.run(
        request.message,
        request.conversation_id,
        request.metadata,
        request.system_prompt,
        request.preferred_model,
        request.preferred_agent,
    )


@app.get("/models")
def list_models() -> list[dict[str, str]]:
    return model_service.list_models()


@app.post("/models/route", response_model=RouteResponse)
def route_model(request: RouteRequest) -> RouteResponse:
    return model_router.route(request.message)


@app.post("/memory/save")
def save_memory(request: MemorySaveRequest) -> dict[str, object]:
    record = memory_service.save(request.record)
    return {"saved": True, "record": record.model_dump(mode="json")}


@app.get("/memory/search", response_model=MemorySearchResponse)
def search_memory(query: str = Query(..., min_length=1)) -> MemorySearchResponse:
    return MemorySearchResponse(query=query, results=memory_service.search(query))


@app.post("/rag/ingest", response_model=RagIngestResponse)
def ingest_rag(request: RagIngestRequest) -> RagIngestResponse:
    return rag_service.ingest(request)


@app.post("/rag/query", response_model=RagQueryResponse)
def query_rag(request: RagQueryRequest) -> RagQueryResponse:
    return rag_service.query(request)


@app.post("/agents/run", response_model=AgentRunResponse)
def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    return agent_service.run(request.agent, request.message)

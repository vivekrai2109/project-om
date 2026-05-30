from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import uuid4

from app.schemas import RagIngestRequest, RagIngestResponse, RagQueryRequest, RagQueryResponse


def chunk_text(content: str, chunk_size: int = 300) -> list[str]:
    return [content[index : index + chunk_size] for index in range(0, len(content), chunk_size)] or [""]


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class MockEmbeddingProvider(EmbeddingProvider):
    def embed(self, text: str) -> list[float]:
        terms = text.lower().split()
        seed = float(sum(len(term) for term in terms) or 1)
        return [seed, float(len(set(terms)) or 1), float(len(text) or 1)]


class VectorSearch(ABC):
    @abstractmethod
    def upsert(self, document_id: str, chunk: str, vector: list[float], metadata: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(self, vector: list[float], top_k: int) -> list[dict]:
        raise NotImplementedError


@dataclass
class VectorRecord:
    document_id: str
    chunk: str
    vector: list[float]
    metadata: dict


class MockVectorStore(VectorSearch):
    def __init__(self) -> None:
        self.records: list[VectorRecord] = []

    def upsert(self, document_id: str, chunk: str, vector: list[float], metadata: dict) -> None:
        self.records.append(VectorRecord(document_id=document_id, chunk=chunk, vector=vector, metadata=metadata))

    def query(self, vector: list[float], top_k: int) -> list[dict]:
        scored = []
        for record in self.records:
            score = sum(abs(left - right) for left, right in zip(record.vector, vector, strict=False))
            scored.append(
                {
                    "document_id": record.document_id,
                    "content": record.chunk,
                    "score": round(score, 3),
                    "metadata": record.metadata,
                }
            )
        return sorted(scored, key=lambda item: item["score"])[:top_k]


class RagService:
    def __init__(self) -> None:
        self.embedding_provider = MockEmbeddingProvider()
        # TODO: replace with pgvector-backed retrieval when PostgreSQL is enabled.
        self.vector_store = MockVectorStore()

    def ingest(self, request: RagIngestRequest) -> RagIngestResponse:
        document_id = str(uuid4())
        chunks = chunk_text(request.content)
        for index, chunk in enumerate(chunks):
            vector = self.embedding_provider.embed(chunk)
            self.vector_store.upsert(
                document_id=document_id,
                chunk=chunk,
                vector=vector,
                metadata={**request.metadata, "title": request.title, "chunk_index": index},
            )
        return RagIngestResponse(
            document_id=document_id,
            chunks_indexed=len(chunks),
            metadata={"title": request.title},
        )

    def query(self, request: RagQueryRequest) -> RagQueryResponse:
        vector = self.embedding_provider.embed(request.query)
        matches = self.vector_store.query(vector=vector, top_k=request.top_k)
        if matches:
            answer = "\n\n".join(match["content"] for match in matches)
        else:
            answer = "No indexed context found yet. Ingest documents first."
        return RagQueryResponse(answer=answer, matches=matches, metadata={"query": request.query})

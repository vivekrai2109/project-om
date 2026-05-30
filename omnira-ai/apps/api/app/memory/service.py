from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.schemas import MemoryRecord


@dataclass
class MemoryNamespace:
    name: str
    records: list[MemoryRecord]


class BaseMemoryStore:
    def save(self, record: MemoryRecord) -> MemoryRecord:
        raise NotImplementedError

    def search(self, query: str) -> list[MemoryRecord]:
        raise NotImplementedError


class JsonMemoryStore(BaseMemoryStore):
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._records = self._load()

    def _load(self) -> list[MemoryRecord]:
        if not self.file_path.exists():
            return []
        raw = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [MemoryRecord.model_validate(item) for item in raw]

    def _persist(self) -> None:
        payload = [record.model_dump(mode="json") for record in self._records]
        self.file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def save(self, record: MemoryRecord) -> MemoryRecord:
        self._records.append(record)
        self._persist()
        return record

    def search(self, query: str) -> list[MemoryRecord]:
        lowered = query.lower()
        return [
            record
            for record in self._records
            if lowered in record.title.lower()
            or lowered in record.content.lower()
            or any(lowered in tag.lower() for tag in record.tags)
        ]


class ConversationMemory:
    def __init__(self, store: BaseMemoryStore) -> None:
        self.namespace = MemoryNamespace(name="conversation", records=[])
        self.store = store

    def save(self, record: MemoryRecord) -> MemoryRecord:
        return self.store.save(record)

    def search(self, query: str) -> list[MemoryRecord]:
        return [record for record in self.store.search(query) if record.type == "conversation"]


class PersonalMemory:
    def __init__(self, store: BaseMemoryStore) -> None:
        self.namespace = MemoryNamespace(name="personal", records=[])
        self.store = store

    def save(self, record: MemoryRecord) -> MemoryRecord:
        return self.store.save(record)

    def search(self, query: str) -> list[MemoryRecord]:
        return [record for record in self.store.search(query) if record.type == "personal"]


class ProjectMemory:
    def __init__(self, store: BaseMemoryStore) -> None:
        self.namespace = MemoryNamespace(name="project", records=[])
        self.store = store

    def save(self, record: MemoryRecord) -> MemoryRecord:
        return self.store.save(record)

    def search(self, query: str) -> list[MemoryRecord]:
        return [record for record in self.store.search(query) if record.type == "project"]


class MemoryService:
    def __init__(self) -> None:
        settings = get_settings()
        # TODO: replace the JSON development store with PostgreSQL-backed persistence.
        self.store = JsonMemoryStore(settings.memory_file)
        self.conversation = ConversationMemory(self.store)
        self.personal = PersonalMemory(self.store)
        self.project = ProjectMemory(self.store)

    def save(self, record: MemoryRecord) -> MemoryRecord:
        return self.store.save(record)

    def search(self, query: str) -> list[MemoryRecord]:
        return self.store.search(query)

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable


@dataclass(slots=True)
class EventRecord:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    task_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


EventHandler = Callable[[EventRecord], None]


class LocalEventBus:
    def __init__(self, *, history_limit: int = 200) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: deque[EventRecord] = deque(maxlen=max(10, history_limit))
        self._lock = RLock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            self._handlers[event_type].append(handler)

    def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        correlation_id: str = "",
        task_id: str = "",
    ) -> EventRecord:
        record = EventRecord(
            event_type=event_type,
            payload=dict(payload or {}),
            correlation_id=str(correlation_id or ""),
            task_id=str(task_id or ""),
        )
        with self._lock:
            self._history.append(record)
            handlers = list(self._handlers.get(event_type, ())) + list(self._handlers.get("*", ()))
        for handler in handlers:
            handler(record)
        return record

    def history(self, *, event_type: str | None = None, limit: int | None = None) -> list[EventRecord]:
        with self._lock:
            items = list(self._history)
        if event_type:
            items = [item for item in items if item.event_type == event_type]
        if limit is not None:
            items = items[-max(0, limit) :]
        return items
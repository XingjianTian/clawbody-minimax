"""Thread-safe, bounded storage for host bridge logs."""

from __future__ import annotations

import re
from collections import deque
from datetime import UTC, datetime
from threading import Lock
from typing import Literal

from .models import LogEntry

REDACTIONS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)\S+"),
)

LogLevel = Literal["debug", "info", "warning", "error"]


class LogStore:
    """Keep a finite, redacted log history addressable by a monotonic cursor."""

    def __init__(self, limit: int = 300) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        self._items: deque[LogEntry] = deque(maxlen=limit)
        self._cursor = 0
        self._lock = Lock()

    def append(self, level: LogLevel, message: str) -> LogEntry:
        """Redact, truncate, and store a log entry."""
        redacted = self._redact(message)[:2000]
        with self._lock:
            self._cursor += 1
            entry = LogEntry(
                id=self._cursor,
                level=level,
                message=redacted,
                created_at=datetime.now(UTC).isoformat(),
            )
            self._items.append(entry)
            return entry

    def after(self, cursor: int) -> dict[str, int | list[dict[str, object]]]:
        """Return entries created after *cursor* and the current cursor."""
        with self._lock:
            items = [entry.model_dump(mode="json") for entry in self._items if entry.id > cursor]
            return {"cursor": self._cursor, "items": items}

    @staticmethod
    def _redact(message: str) -> str:
        for pattern in REDACTIONS:
            message = pattern.sub(r"\1[REDACTED]", message)
        return message

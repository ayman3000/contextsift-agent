from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import sqlite3

from .models import Message


class SearchIndex:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as connection:
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS records USING fts5(id UNINDEXED, source, content, timestamp UNINDEXED)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def add(self, *, record_id: str, source: str, content: str, timestamp: str = "") -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM records WHERE id = ?", (record_id,))
            connection.execute(
                "INSERT INTO records(id, source, content, timestamp) VALUES (?, ?, ?, ?)",
                (record_id, source, content, timestamp),
            )

    def add_message(self, message: Message) -> None:
        self.add(
            record_id=message.id,
            source=f"conversation:{message.role}",
            content=message.content,
            timestamp=message.timestamp,
        )

    def search(self, query: str, limit: int = 5, exclude_ids: set[str] | None = None) -> list[dict[str, Any]]:
        terms = re.findall(r"[A-Za-z0-9_]{3,}", query.casefold())
        if not terms or limit <= 0:
            return []
        fts_query = " OR ".join(f'"{term}"' for term in dict.fromkeys(terms[:12]))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, source, snippet(records, 2, '[', ']', ' … ', 18), timestamp, bm25(records) "
                "FROM records WHERE records MATCH ? ORDER BY bm25(records) LIMIT ?",
                (fts_query, limit + len(exclude_ids or set())),
            ).fetchall()
        excluded = exclude_ids or set()
        return [
            {"id": row[0], "source": row[1], "excerpt": row[2], "timestamp": row[3], "score": row[4]}
            for row in rows
            if row[0] not in excluded
        ][:limit]

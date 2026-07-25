from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json

from .models import Message


class HistoryStore:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.conversation_path = data_dir / "conversation.jsonl"
        self.tool_calls_path = data_dir / "tool_calls.jsonl"

    @staticmethod
    def _append(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _records(path: Path) -> Iterable[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def append_message(self, message: Message) -> None:
        self._append(self.conversation_path, message.to_record())

    def main_messages(self, limit: int = 0) -> list[Message]:
        if limit < 0:
            raise ValueError("limit must be 0 or a positive integer")
        messages = [
            Message.from_record(record)
            for record in self._records(self.conversation_path)
            if record.get("kind") == "main" and record.get("role") in {"user", "assistant"}
        ]
        return messages if limit == 0 else messages[-limit:]

    def append_tool_receipt(self, record: dict[str, Any]) -> None:
        self._append(self.tool_calls_path, record)

    def recent_tool_receipts(self, limit: int = 20) -> list[dict[str, Any]]:
        records = list(self._records(self.tool_calls_path))
        return records if limit == 0 else records[-limit:]

    def all_tool_receipts(self) -> list[dict[str, Any]]:
        return list(self._records(self.tool_calls_path))

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from .config import Settings
from .history_store import HistoryStore
from .models import estimate_tokens, new_id


@dataclass(slots=True)
class BuiltContext:
    messages: list[dict[str, Any]]
    manifest: dict[str, Any]


class ContextBuilder:
    def __init__(self, settings: Settings, history: HistoryStore):
        self.settings = settings
        self.history = history

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def build(self, retrieved: list[dict[str, Any]] | None = None) -> BuiltContext:
        sources: list[dict[str, Any]] = []
        messages: list[dict[str, Any]] = []

        stable_parts = []
        for name in ("agent.md", "user.md"):
            content = self._read(self.settings.prompts_dir / name)
            if content:
                stable_parts.append(content)
                sources.append({"source": name, "tokens": estimate_tokens(content), "reason": "stable identity"})
        if stable_parts:
            messages.append({"role": "system", "content": "\n\n".join(stable_parts)})

        volatile_parts = []
        for name, reason in (("memory.md", "durable memory"), ("state.md", "current task state")):
            content = self._read(self.settings.prompts_dir / name)
            if content:
                volatile_parts.append(content)
                sources.append({"source": name, "tokens": estimate_tokens(content), "reason": reason})

        if retrieved:
            retrieval_text = "Retrieved historical excerpts:\n" + "\n".join(
                f"- [{item['id']}] {item['excerpt']}" for item in retrieved
            )
            volatile_parts.append(retrieval_text)
            sources.append(
                {"source": "retrieval", "tokens": estimate_tokens(retrieval_text), "reason": "query relevance"}
            )

        receipts = self.history.recent_tool_receipts(self.settings.context.tool_ledger_entries)
        if receipts:
            ledger = "Recent tool ledger:\n" + "\n".join(
                f"- {item['call_id']} {item['tool']} → {item['summary']}"
                + (f" [{', '.join(item.get('artifact_ids', []))}]" if item.get("artifact_ids") else "")
                for item in receipts
            )
            volatile_parts.append(ledger)
            sources.append({"source": "tool-ledger", "tokens": estimate_tokens(ledger), "reason": "avoid duplicate calls"})

        if volatile_parts:
            messages.append({"role": "system", "content": "\n\n".join(volatile_parts)})

        recent_limit = self.settings.context.recent_main_messages
        main_messages = self.history.main_messages(recent_limit)
        messages.extend(message.to_model_message() for message in main_messages)
        history_text = "\n".join(message.content for message in main_messages)
        sources.append(
            {
                "source": "conversation:all" if recent_limit == 0 else f"conversation:last-{recent_limit}",
                "tokens": estimate_tokens(history_text) if history_text else 0,
                "reason": "main message history",
                "message_count": len(main_messages),
            }
        )

        total = sum(estimate_tokens(str(message.get("content", ""))) for message in messages)
        manifest = {
            "request_id": new_id("request"),
            "estimated_input_tokens": total,
            "max_input_tokens": self.settings.context.max_input_tokens,
            "over_budget": total > self.settings.context.max_input_tokens,
            "recent_main_messages_setting": recent_limit,
            "sources": sources,
        }
        return BuiltContext(messages=messages, manifest=manifest)

    def save_manifest(self, manifest: dict[str, Any]) -> Path:
        path = self.settings.data_dir / "context_manifests.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest, ensure_ascii=False) + "\n")
        return path

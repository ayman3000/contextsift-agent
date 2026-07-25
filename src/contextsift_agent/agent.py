from __future__ import annotations

from typing import Any
import json
import os

from .artifact_store import ArtifactStore
from .config import Settings
from .context_builder import ContextBuilder
from .history_store import HistoryStore
from .models import Message, ModelResponse, estimate_tokens, new_id
from .provider import ChatCompletionsProvider, ModelProvider
from .retrieval import SearchIndex
from .tool_registry import ToolRegistry
from .tools import (
    register_artifact_tools,
    register_code_tools,
    register_filesystem_tools,
    register_terminal_tools,
    register_web_tools,
)


class Agent:
    def __init__(
        self,
        settings: Settings,
        provider: ModelProvider | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.settings = settings
        self.history = HistoryStore(settings.data_dir)
        self.artifacts = ArtifactStore(settings.data_dir)
        self.search_index = SearchIndex(settings.data_dir / "search.sqlite")
        self.context_builder = ContextBuilder(settings, self.history)
        self.provider = provider or ChatCompletionsProvider(settings.agent)
        self.registry = registry or self._default_registry()
        self._reindex_persisted_history()

    def _default_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        register_filesystem_tools(
            registry,
            [self.settings.root],
            self.artifacts,
            self.settings.tools.max_preview_bytes,
        )
        register_terminal_tools(
            registry,
            self.settings.root,
            self.artifacts,
            self.settings.tools.default_timeout_seconds,
            self.settings.tools.max_preview_bytes,
        )
        register_web_tools(
            registry,
            self.settings.web.api_key_env,
            self.settings.web.max_results,
            self.artifacts,
            self.settings.tools.max_preview_bytes,
        )
        register_code_tools(
            registry,
            self.settings.data_dir,
            self.artifacts,
            self.settings.tools.max_preview_bytes,
        )
        register_artifact_tools(registry, self.artifacts)
        return registry

    def _reindex_persisted_history(self) -> None:
        for message in self.history.main_messages(0):
            self.search_index.add_message(message)
        for receipt in self.history.all_tool_receipts():
            self.search_index.add(
                record_id=receipt["call_id"],
                source=f"tool:{receipt['tool']}",
                content=f"{receipt.get('summary', '')}\n{receipt.get('preview', '')}",
                timestamp=receipt.get("timestamp", ""),
            )

    def _retrieval(self, query: str) -> list[dict[str, Any]]:
        # Unlimited history already contains every main message; injecting retrieved
        # duplicates would waste context and weaken the prompt-cache prefix.
        if self.settings.context.recent_main_messages == 0:
            return []
        recent = self.history.main_messages(self.settings.context.recent_main_messages)
        return self.search_index.search(
            query,
            limit=self.settings.context.retrieved_history_results,
            exclude_ids={message.id for message in recent},
        )

    @staticmethod
    def _assistant_tool_message(response: ModelResponse) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                for call in response.tool_calls
            ],
        }

    @staticmethod
    def _compact_consumed_tool_results(active_sequence: list[dict[str, Any]]) -> None:
        """Replace already-consumed previews with compact receipts for later steps."""
        for message in active_sequence:
            if message.get("role") != "tool":
                continue
            try:
                result = json.loads(message.get("content") or "{}")
            except json.JSONDecodeError:
                continue
            if result.get("compacted"):
                continue
            compact = {
                "call_id": result.get("call_id"),
                "tool": result.get("tool"),
                "status": result.get("status"),
                "summary": result.get("summary"),
                "artifact_ids": result.get("artifact_ids", []),
                "truncated": result.get("truncated", False),
                "error": result.get("error"),
                "compacted": True,
            }
            message["content"] = json.dumps(compact, ensure_ascii=False)

    def _request_manifest(
        self,
        base_manifest: dict[str, Any],
        schemas: list[dict[str, Any]],
        active_sequence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sources = [dict(item) for item in base_manifest["sources"]]
        schema_text = json.dumps(schemas, ensure_ascii=False, sort_keys=True)
        schema_tokens = estimate_tokens(schema_text) if schemas else 0
        sources.append(
            {
                "source": "tool-schemas",
                "tokens": schema_tokens,
                "reason": "tools available for this model call",
                "tool_count": len(schemas),
            }
        )
        active_text = json.dumps(active_sequence, ensure_ascii=False)
        active_tokens = estimate_tokens(active_text) if active_sequence else 0
        sources.append(
            {
                "source": "active-tool-sequence",
                "tokens": active_tokens,
                "reason": "unfinished current turn",
                "message_count": len(active_sequence),
            }
        )
        total = base_manifest["estimated_input_tokens"] + schema_tokens + active_tokens
        return {
            **base_manifest,
            "request_id": new_id("request"),
            "estimated_input_tokens": total,
            "over_budget": total > self.settings.context.max_input_tokens,
            "sources": sources,
        }

    def ask(self, text: str) -> str:
        if not text.strip():
            raise ValueError("User message cannot be empty")
        turn_id = new_id("turn")
        user_message = Message(role="user", content=text, turn_id=turn_id)
        self.history.append_message(user_message)
        self.search_index.add_message(user_message)

        retrieved = self._retrieval(text)
        built = self.context_builder.build(retrieved)
        active_sequence: list[dict[str, Any]] = []
        calls_used = 0
        schemas = self.registry.schemas()

        while True:
            manifest = self._request_manifest(built.manifest, schemas, active_sequence)
            self.context_builder.save_manifest(manifest)
            response = self.provider.complete(built.messages + active_sequence, schemas)
            if not response.tool_calls:
                content = response.content or ""
                assistant_message = Message(role="assistant", content=content, turn_id=turn_id)
                self.history.append_message(assistant_message)
                self.search_index.add_message(assistant_message)
                return content

            if calls_used + len(response.tool_calls) > self.settings.agent.max_tool_calls_per_turn:
                raise RuntimeError(
                    f"Tool-call limit exceeded ({self.settings.agent.max_tool_calls_per_turn} per turn)"
                )
            self._compact_consumed_tool_results(active_sequence)
            active_sequence.append(self._assistant_tool_message(response))

            for call in response.tool_calls:
                calls_used += 1
                result = self.registry.execute(call.name, call.arguments, call.id)
                self.history.append_tool_receipt(result.to_record(call.arguments, turn_id))
                self.search_index.add(
                    record_id=result.call_id,
                    source=f"tool:{result.tool}",
                    content=f"{result.summary}\n{result.preview}",
                    timestamp=result.timestamp,
                )
                active_sequence.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result.to_model_content()}
                )

    def preview_context(self, query: str | None = None) -> dict[str, Any]:
        retrieved = self._retrieval(query) if query else []
        built = self.context_builder.build(retrieved)
        manifest = self._request_manifest(built.manifest, self.registry.schemas(), [])
        return {"messages": built.messages, "manifest": manifest}

    def doctor(self) -> dict[str, Any]:
        schema_names = [item["function"]["name"] for item in self.registry.schemas()]
        model_key_configured = bool(
            self.settings.agent.api_key_env and os.environ.get(self.settings.agent.api_key_env)
        )
        model_ready = not self.settings.agent.api_key_required or model_key_configured
        return {
            "status": "ready" if model_ready else "needs_api_key",
            "python_source_execution": True,
            "model": self.settings.agent.model,
            "base_url": self.settings.agent.base_url,
            "recent_main_messages": self.settings.context.recent_main_messages,
            "conversation_mode": "all" if self.settings.context.recent_main_messages == 0 else "bounded",
            "model_api_key_env": self.settings.agent.api_key_env,
            "model_api_key_required": self.settings.agent.api_key_required,
            "model_api_key_configured": model_key_configured,
            "tavily_api_key_env": self.settings.web.api_key_env,
            "tavily_api_key_configured": bool(os.environ.get(self.settings.web.api_key_env)),
            "sqlite_fts5": True,
            "data_directory": str(self.settings.data_dir),
            "tool_count": len(schema_names),
            "tools": schema_names,
            "notes": [
                "Tavily is optional unless web_search is called.",
                "Python execution is process-isolated but not a hardened network or memory sandbox.",
            ],
        }

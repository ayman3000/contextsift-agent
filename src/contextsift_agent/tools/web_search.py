from __future__ import annotations

from urllib import error, request
import json
import os
import ssl

from ..artifact_store import ArtifactStore
from ..models import ToolResult
from ..tool_registry import ToolRegistry


def _https_context() -> ssl.SSLContext:
    """Prefer certifi when present; some macOS Python installs lack a usable CA bundle."""
    try:
        import certifi  # type: ignore[import-not-found]
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


class TavilyTools:
    def __init__(self, api_key_env: str, max_results: int, artifacts: ArtifactStore, max_preview_bytes: int):
        self.api_key_env = api_key_env
        self.max_results = max_results
        self.artifacts = artifacts
        self.max_preview_bytes = max_preview_bytes

    def search(self, query: str, max_results: int | None = None, *, call_id: str) -> ToolResult:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            return ToolResult(call_id, "web_search", "error", "Tavily API key is not configured", error=f"Missing {self.api_key_env}")
        count = min(max_results or self.max_results, self.max_results)
        payload = json.dumps({"api_key": api_key, "query": query, "max_results": count}).encode("utf-8")
        http_request = request.Request(
            "https://api.tavily.com/search",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(http_request, timeout=45, context=_https_context()) as response:
                raw = json.loads(response.read())
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return ToolResult(call_id, "web_search", "error", f"Tavily returned HTTP {exc.code}", preview=detail[:2000], error="http error")
        except error.URLError as exc:
            return ToolResult(
                call_id,
                "web_search",
                "error",
                "Tavily request failed",
                error=f"{type(exc.reason).__name__}: {exc.reason}",
            )
        results = [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("content"),
                "score": item.get("score"),
            }
            for item in raw.get("results", [])[:count]
        ]
        text = json.dumps(results, ensure_ascii=False, indent=2)
        encoded = text.encode("utf-8")
        artifact_ids = []
        truncated = len(encoded) > self.max_preview_bytes
        if truncated:
            artifact_ids.append(self.artifacts.save_bytes(encoded, suffix=".json", description="Complete Tavily search results", call_id=call_id)["id"])
        return ToolResult(
            call_id,
            "web_search",
            "success",
            f"Tavily returned {len(results)} results",
            encoded[: self.max_preview_bytes].decode("utf-8", errors="replace"),
            artifact_ids,
            truncated,
            metadata={"result_count": len(results)},
        )


def register_web_tools(
    registry: ToolRegistry,
    api_key_env: str,
    max_results: int,
    artifacts: ArtifactStore,
    max_preview_bytes: int,
) -> None:
    tools = TavilyTools(api_key_env, max_results, artifacts, max_preview_bytes)
    registry.register(
        "web_search",
        "Search the current web with Tavily and return structured source snippets and URLs.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "minimum": 1, "maximum": 10}},
            "required": ["query"],
        },
        tools.search,
    )

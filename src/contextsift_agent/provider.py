from __future__ import annotations

from typing import Any, Protocol
from urllib import error, request
import json
import os

from .config import AgentSettings
from .models import ModelResponse, ToolCall


class ModelProvider(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelResponse: ...


class ChatCompletionsProvider:
    """Small dependency-free adapter for OpenAI-compatible chat-completions APIs."""

    def __init__(self, settings: AgentSettings):
        self.settings = settings

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelResponse:
        api_key = os.environ.get(self.settings.api_key_env) if self.settings.api_key_env else None
        if self.settings.api_key_required and not api_key:
            raise RuntimeError(f"Missing API key environment variable: {self.settings.api_key_env}")
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        body = json.dumps(payload).encode("utf-8")
        endpoint = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        http_request = request.Request(endpoint, data=body, method="POST", headers=headers)
        try:
            with request.urlopen(http_request, timeout=self.settings.request_timeout_seconds) as response:
                raw = json.loads(response.read())
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Model API returned HTTP {exc.code}: {detail[:2000]}") from exc
        message = raw["choices"][0]["message"]
        tool_calls = []
        for item in message.get("tool_calls") or []:
            try:
                arguments = json.loads(item["function"].get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Model returned invalid JSON tool arguments for {item['function']['name']}") from exc
            tool_calls.append(ToolCall(id=item["id"], name=item["function"]["name"], arguments=arguments))
        return ModelResponse(content=message.get("content"), tool_calls=tool_calls, raw=raw)

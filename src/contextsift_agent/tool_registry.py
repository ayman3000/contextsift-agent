from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import time

from .models import ToolResult, new_id


ToolHandler = Callable[..., ToolResult]


@dataclass(slots=True)
class RegisteredTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = RegisteredTool(name, description, parameters, handler)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any], call_id: str | None = None) -> ToolResult:
        resolved_call_id = call_id or new_id("call")
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                call_id=resolved_call_id,
                tool=name,
                status="error",
                summary="Unknown tool",
                error=f"No tool named {name!r} is registered",
            )
        started = time.monotonic()
        try:
            result = tool.handler(call_id=resolved_call_id, **arguments)
        except TypeError as exc:
            result = ToolResult(
                call_id=resolved_call_id,
                tool=name,
                status="error",
                summary="Invalid tool arguments",
                error=str(exc),
            )
        except Exception as exc:  # Tool failures are data returned to the model.
            result = ToolResult(
                call_id=resolved_call_id,
                tool=name,
                status="error",
                summary="Tool execution failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        result.duration_ms = int((time.monotonic() - started) * 1000)
        return result

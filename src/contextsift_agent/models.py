from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
import json
import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_tokens(text: str) -> int:
    """A dependency-free approximation used for manifests, not provider billing."""
    return max(1, (len(text) + 3) // 4)


@dataclass(slots=True)
class Message:
    role: Literal["user", "assistant"]
    content: str
    id: str = field(default_factory=lambda: new_id("msg"))
    turn_id: str = field(default_factory=lambda: new_id("turn"))
    timestamp: str = field(default_factory=utc_now)
    kind: str = "main"
    tags: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["token_count"] = estimate_tokens(self.content)
        return record

    def to_model_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "Message":
        values = {key: record[key] for key in cls.__dataclass_fields__ if key in record}
        return cls(**values)


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ModelResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolResult:
    call_id: str
    tool: str
    status: Literal["success", "error", "denied"]
    summary: str
    preview: str = ""
    artifact_ids: list[str] = field(default_factory=list)
    truncated: bool = False
    duration_ms: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)

    def to_record(self, arguments: dict[str, Any], turn_id: str) -> dict[str, Any]:
        record = asdict(self)
        record["arguments"] = arguments
        record["turn_id"] = turn_id
        return record

    def to_model_content(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def ledger_line(self) -> str:
        artifact = f" [{', '.join(self.artifact_ids)}]" if self.artifact_ids else ""
        return f"{self.call_id} {self.tool} → {self.summary}{artifact}"

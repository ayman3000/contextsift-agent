from __future__ import annotations

import json

from ..artifact_store import ArtifactStore
from ..models import ToolResult
from ..tool_registry import ToolRegistry


class ArtifactTools:
    def __init__(self, artifacts: ArtifactStore):
        self.artifacts = artifacts

    def read(self, artifact_id: str, offset: int = 0, limit: int = 12_000, *, call_id: str) -> ToolResult:
        value = self.artifacts.read(artifact_id, offset, limit)
        return ToolResult(
            call_id,
            "artifact_read",
            "success",
            f"Read artifact bytes {offset}–{offset + len(value['content'].encode('utf-8'))}",
            value["content"],
            metadata={"artifact_id": artifact_id, "has_more": value["has_more"], "total_bytes": value["total_bytes"]},
        )

    def search(self, artifact_id: str, query: str, max_matches: int = 10, *, call_id: str) -> ToolResult:
        matches = self.artifacts.search(artifact_id, query, max_matches)
        return ToolResult(
            call_id,
            "artifact_search",
            "success",
            f"Found {len(matches)} matches",
            json.dumps(matches, ensure_ascii=False, indent=2),
            metadata={"artifact_id": artifact_id},
        )


def register_artifact_tools(registry: ToolRegistry, artifacts: ArtifactStore) -> None:
    tools = ArtifactTools(artifacts)
    registry.register(
        "artifact_read",
        "Read a bounded byte range from a stored tool artifact.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "artifact_id": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50000},
            },
            "required": ["artifact_id"],
        },
        tools.read,
    )
    registry.register(
        "artifact_search",
        "Search within a stored text artifact without loading all of it.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "artifact_id": {"type": "string"},
                "query": {"type": "string"},
                "max_matches": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["artifact_id", "query"],
        },
        tools.search,
    )

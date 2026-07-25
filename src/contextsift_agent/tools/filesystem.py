from __future__ import annotations

from pathlib import Path
import os
import re

from ..artifact_store import ArtifactStore
from ..models import ToolResult
from ..tool_registry import ToolRegistry


class FilesystemTools:
    def __init__(self, roots: list[Path], artifacts: ArtifactStore, max_preview_bytes: int):
        self.roots = [root.resolve() for root in roots]
        self.artifacts = artifacts
        self.max_preview_bytes = max_preview_bytes

    def _resolve(self, value: str) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.roots[0] / candidate
        resolved = candidate.resolve()
        if not any(resolved == root or root in resolved.parents for root in self.roots):
            raise PermissionError(f"Path is outside configured workspace roots: {value}")
        return resolved

    def _bounded(self, call_id: str, tool: str, text: str, summary: str) -> ToolResult:
        encoded = text.encode("utf-8")
        if len(encoded) <= self.max_preview_bytes:
            return ToolResult(call_id=call_id, tool=tool, status="success", summary=summary, preview=text)
        artifact = self.artifacts.save_bytes(
            encoded,
            suffix=".txt",
            description=f"Complete output from {tool}",
            call_id=call_id,
        )
        preview = encoded[: self.max_preview_bytes].decode("utf-8", errors="replace")
        return ToolResult(
            call_id=call_id,
            tool=tool,
            status="success",
            summary=summary,
            preview=preview,
            artifact_ids=[artifact["id"]],
            truncated=True,
            metadata={"total_bytes": len(encoded)},
        )

    def list_directory(self, path: str = ".", limit: int = 200, *, call_id: str) -> ToolResult:
        target = self._resolve(path)
        if not target.is_dir():
            raise NotADirectoryError(path)
        entries = []
        for entry in sorted(target.iterdir(), key=lambda item: item.name.casefold())[:limit]:
            kind = "dir" if entry.is_dir() else "file"
            size = entry.stat().st_size if entry.is_file() else 0
            entries.append(f"{kind:4} {size:10} {entry.name}")
        return self._bounded(call_id, "filesystem_list_directory", "\n".join(entries), f"Listed {len(entries)} entries")

    def stat(self, path: str, *, call_id: str) -> ToolResult:
        target = self._resolve(path)
        stat = target.stat()
        preview = (
            f"path={target}\nkind={'directory' if target.is_dir() else 'file'}\n"
            f"bytes={stat.st_size}\nmodified_ns={stat.st_mtime_ns}"
        )
        return ToolResult(call_id, "filesystem_stat", "success", "Path metadata collected", preview)

    def read_file(self, path: str, start_line: int = 1, line_count: int = 200, *, call_id: str) -> ToolResult:
        if start_line < 1 or line_count <= 0:
            raise ValueError("start_line must be >= 1 and line_count must be positive")
        target = self._resolve(path)
        if b"\x00" in target.read_bytes()[:4096]:
            raise ValueError("Binary files cannot be read as text")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[start_line - 1 : start_line - 1 + line_count]
        text = "\n".join(f"{number}: {line}" for number, line in enumerate(selected, start=start_line))
        result = self._bounded(call_id, "filesystem_read_file", text, f"Read {len(selected)} of {len(lines)} lines")
        result.metadata.update({"total_lines": len(lines), "start_line": start_line})
        return result

    def search_text(self, query: str, path: str = ".", limit: int = 100, *, call_id: str) -> ToolResult:
        target = self._resolve(path)
        paths = [target] if target.is_file() else (item for item in target.rglob("*") if item.is_file())
        matches = []
        for file_path in paths:
            if any(part in {".git", ".venv", "__pycache__"} for part in file_path.parts):
                continue
            try:
                if file_path.stat().st_size > 5_000_000:
                    continue
                for number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
                    if query.casefold() in line.casefold():
                        matches.append(f"{file_path.relative_to(self.roots[0])}:{number}: {line[:500]}")
                        if len(matches) >= limit:
                            break
            except (UnicodeDecodeError, OSError, ValueError):
                continue
            if len(matches) >= limit:
                break
        return self._bounded(call_id, "filesystem_search_text", "\n".join(matches), f"Found {len(matches)} matches")

    def write_file(self, path: str, content: str, overwrite: bool = False, *, call_id: str) -> ToolResult:
        target = self._resolve(path)
        if target.exists() and not overwrite:
            return ToolResult(call_id, "filesystem_write_file", "denied", "File already exists", error="Set overwrite=true explicitly")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(call_id, "filesystem_write_file", "success", f"Wrote {len(content.encode('utf-8'))} bytes", str(target))


def register_filesystem_tools(
    registry: ToolRegistry,
    roots: list[Path],
    artifacts: ArtifactStore,
    max_preview_bytes: int,
) -> None:
    tools = FilesystemTools(roots, artifacts, max_preview_bytes)
    object_schema = {"type": "object", "additionalProperties": False}
    registry.register(
        "filesystem_list_directory",
        "List a directory inside the configured workspace.",
        {**object_schema, "properties": {"path": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 1000}}},
        tools.list_directory,
    )
    registry.register(
        "filesystem_stat",
        "Get metadata for a workspace path.",
        {**object_schema, "properties": {"path": {"type": "string"}}, "required": ["path"]},
        tools.stat,
    )
    registry.register(
        "filesystem_read_file",
        "Read a numbered slice of a UTF-8 text file.",
        {
            **object_schema,
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "line_count": {"type": "integer", "minimum": 1, "maximum": 2000},
            },
            "required": ["path"],
        },
        tools.read_file,
    )
    registry.register(
        "filesystem_search_text",
        "Search text files below a workspace path.",
        {
            **object_schema,
            "properties": {"query": {"type": "string"}, "path": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "required": ["query"],
        },
        tools.search_text,
    )
    registry.register(
        "filesystem_write_file",
        "Create or explicitly overwrite a UTF-8 text file inside the workspace.",
        {
            **object_schema,
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "overwrite": {"type": "boolean"}},
            "required": ["path", "content"],
        },
        tools.write_file,
    )

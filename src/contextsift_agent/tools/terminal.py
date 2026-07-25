from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess

from ..artifact_store import ArtifactStore
from ..models import ToolResult
from ..tool_registry import ToolRegistry


class TerminalTools:
    DENIED_PROGRAMS = {"rm", "rmdir", "shutdown", "reboot", "mkfs", "dd"}

    def __init__(self, root: Path, artifacts: ArtifactStore, default_timeout: int, max_preview_bytes: int):
        self.root = root.resolve()
        self.artifacts = artifacts
        self.default_timeout = default_timeout
        self.max_preview_bytes = max_preview_bytes

    def _cwd(self, value: str) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        if not (resolved == self.root or self.root in resolved.parents):
            raise PermissionError("Terminal cwd is outside the workspace")
        return resolved

    def run(self, command: str, cwd: str = ".", timeout_seconds: int | None = None, *, call_id: str) -> ToolResult:
        args = shlex.split(command)
        if not args:
            raise ValueError("command cannot be empty")
        if Path(args[0]).name in self.DENIED_PROGRAMS:
            return ToolResult(call_id, "terminal_run", "denied", "Destructive command denied", error=args[0])
        timeout = timeout_seconds or self.default_timeout
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
        }
        try:
            completed = subprocess.run(
                args,
                cwd=self._cwd(cwd),
                env=environment,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or b"") + (exc.stderr or b"")
            artifact_ids = []
            if output:
                artifact_ids.append(self.artifacts.save_bytes(output, suffix=".log", description="Timed-out terminal output", call_id=call_id)["id"])
            return ToolResult(call_id, "terminal_run", "error", f"Command timed out after {timeout}s", artifact_ids=artifact_ids, error="timeout")
        combined = completed.stdout + (b"\n[stderr]\n" + completed.stderr if completed.stderr else b"")
        truncated = len(combined) > self.max_preview_bytes
        artifact_ids = []
        if truncated:
            artifact_ids.append(self.artifacts.save_bytes(combined, suffix=".log", description="Complete terminal output", call_id=call_id)["id"])
        preview = combined[: self.max_preview_bytes].decode("utf-8", errors="replace")
        status = "success" if completed.returncode == 0 else "error"
        return ToolResult(
            call_id,
            "terminal_run",
            status,
            f"Command exited with code {completed.returncode}",
            preview,
            artifact_ids,
            truncated,
            error=None if completed.returncode == 0 else "non-zero exit code",
            metadata={"exit_code": completed.returncode, "output_bytes": len(combined)},
        )


def register_terminal_tools(
    registry: ToolRegistry,
    root: Path,
    artifacts: ArtifactStore,
    default_timeout: int,
    max_preview_bytes: int,
) -> None:
    tools = TerminalTools(root, artifacts, default_timeout, max_preview_bytes)
    registry.register(
        "terminal_run",
        "Run one non-destructive executable in the workspace without shell expansion or pipelines.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300},
            },
            "required": ["command"],
        },
        tools.run,
    )

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import mimetypes

from .models import new_id, utc_now


class ArtifactStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "artifacts"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = data_dir / "artifacts.jsonl"

    def save_bytes(
        self,
        content: bytes,
        *,
        suffix: str = ".bin",
        description: str = "",
        call_id: str | None = None,
    ) -> dict[str, Any]:
        artifact_id = new_id("artifact")
        path = self.root / f"{artifact_id}{suffix}"
        path.write_bytes(content)
        metadata = {
            "id": artifact_id,
            "path": str(path),
            "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "created_at": utc_now(),
            "description": description,
            "call_id": call_id,
        }
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata, ensure_ascii=False) + "\n")
        return metadata

    def save_text(self, content: str, **kwargs: Any) -> dict[str, Any]:
        suffix = kwargs.pop("suffix", ".txt")
        return self.save_bytes(content.encode("utf-8"), suffix=suffix, **kwargs)

    def metadata(self, artifact_id: str) -> dict[str, Any]:
        if self.index_path.exists():
            with self.index_path.open(encoding="utf-8") as handle:
                for line in handle:
                    record = json.loads(line)
                    if record["id"] == artifact_id:
                        return record
        raise KeyError(f"Unknown artifact: {artifact_id}")

    def read(self, artifact_id: str, offset: int = 0, limit: int = 12_000) -> dict[str, Any]:
        if offset < 0 or limit <= 0:
            raise ValueError("offset must be non-negative and limit must be positive")
        metadata = self.metadata(artifact_id)
        content = Path(metadata["path"]).read_bytes()
        chunk = content[offset : offset + limit]
        return {
            "artifact_id": artifact_id,
            "offset": offset,
            "content": chunk.decode("utf-8", errors="replace"),
            "has_more": offset + len(chunk) < len(content),
            "total_bytes": len(content),
        }

    def search(self, artifact_id: str, query: str, max_matches: int = 10) -> list[dict[str, Any]]:
        metadata = self.metadata(artifact_id)
        text = Path(metadata["path"]).read_text(encoding="utf-8", errors="replace")
        matches = []
        for number, line in enumerate(text.splitlines(), start=1):
            if query.casefold() in line.casefold():
                matches.append({"line": number, "text": line[:500]})
                if len(matches) >= max_matches:
                    break
        return matches

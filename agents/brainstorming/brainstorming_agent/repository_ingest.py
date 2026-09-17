from __future__ import annotations

from pathlib import Path

from .vector_store import VectorStore

IGNORED = {".git", ".venv", "__pycache__", "node_modules", "data", ".env"}
EXTENSIONS = {".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".json"}


def ingest_repository(root: Path, store: VectorStore) -> int:
    """Index safe source and documentation files, excluding credentials and data."""
    count = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if any(part in IGNORED or part.startswith(".env") for part in path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        if text.strip():
            store.index_file(path.relative_to(root), text)
            count += 1
    return count

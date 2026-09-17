import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        safe = {k: v for k, v in fields.items() if k.lower() not in {"token", "password", "authorization"}}
        safe.update(event=event, timestamp=datetime.now(timezone.utc).isoformat())
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(safe, default=str) + "\n")

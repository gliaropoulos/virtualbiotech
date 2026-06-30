"""Per-session workspace + audit log.

Each Virtual Biotech run gets an isolated directory holding the reproducible artifacts the paper
emphasizes: a JSONL reasoning/tool trace, plus space for generated code, figures, and data. A human
expert can replay any result from this directory.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .. import config


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    root: Path = field(default=config.SESSIONS_DIR)

    def __post_init__(self) -> None:
        self.dir = Path(self.root) / self.session_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.trace = self.dir / "trace.jsonl"

    def log(self, event: str, payload: dict | None = None) -> None:
        """Append a structured event to the audit trace."""
        rec = {"t": time.time(), "event": event, "payload": payload or {}}
        with self.trace.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def read_trace(self) -> list[dict]:
        if not self.trace.exists():
            return []
        return [json.loads(line) for line in self.trace.read_text().splitlines() if line.strip()]

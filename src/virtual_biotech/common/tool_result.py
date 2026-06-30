"""Standard MCP tool return envelope: a summary, the typed data, and a small preview."""
from __future__ import annotations

from typing import Any


def tool_result(summary: str, data: Any, preview: Any | None = None) -> dict:
    """Wrap a tool's output for LLM consumption.

    summary: one or two sentences a model can read to decide whether to dig deeper.
    data:    the full structured payload.
    preview: an optional small slice (e.g. first few rows) for quick triage.
    """
    return {"summary": summary, "data": data, "preview": preview}

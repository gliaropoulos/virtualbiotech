"""System-prompt loader. Prompts live as .md files next to this module."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load a system prompt by stem (e.g. 'cso', 'clinical_trialist')."""
    path = _DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"No system prompt '{name}' at {path}")
    return path.read_text(encoding="utf-8")


def available() -> list[str]:
    return sorted(p.stem for p in _DIR.glob("*.md"))

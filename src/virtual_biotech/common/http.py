"""Shared async HTTP client with retry/backoff for MCP tool implementations."""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def client(**kwargs) -> httpx.AsyncClient:
    """Create a configured async client. Callers should use it as a context manager."""
    kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)
    kwargs.setdefault("headers", {"User-Agent": "virtual-biotech/0.1 (research)"})
    return httpx.AsyncClient(**kwargs)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.5, max=8), reraise=True)
async def get_json(url: str, *, params: dict | None = None, **kwargs) -> dict:
    async with client() as c:
        resp = await c.get(url, params=params, **kwargs)
        resp.raise_for_status()
        return resp.json()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.5, max=8), reraise=True)
async def post_json(url: str, *, json: dict, **kwargs) -> dict:
    async with client() as c:
        resp = await c.post(url, json=json, **kwargs)
        resp.raise_for_status()
        return resp.json()

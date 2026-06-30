"""Massively-parallel trial-extraction harness.

The paper dispatched 37,075 clinical-trialist agents to curate Phase II/III trials in ~6 hours by
giving each agent one NCT ID and its full context window. This harness reproduces that pattern:
bounded concurrency, per-trial JSON output, and checkpointing so an interrupted run resumes without
re-doing completed trials. The per-trial extractor is injected (the cascade + agent in production,
a stub in tests), so the harness itself is unit-testable without any model calls.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from .schema import ClinicalTrialData

# extractor: nct_id -> validated record
Extractor = Callable[[str], Awaitable[ClinicalTrialData]]


@dataclass
class RunStats:
    total: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    started_at: float = field(default_factory=time.time)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def elapsed_s(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> dict:
        return {"total": self.total, "completed": self.completed, "skipped": self.skipped,
                "failed": self.failed, "elapsed_s": round(self.elapsed_s, 2),
                "throughput_per_s": round(self.completed / self.elapsed_s, 2) if self.elapsed_s else None}


class ExtractionHarness:
    def __init__(self, out_dir: str | Path, *, concurrency: int = 32,
                 min_interval_s: float = 0.0):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.concurrency = concurrency
        self.min_interval_s = min_interval_s          # simple global rate limit
        self._sem = asyncio.Semaphore(concurrency)
        self._rate_lock = asyncio.Lock()
        self._last_call = 0.0

    def output_path(self, nct_id: str) -> Path:
        return self.out_dir / f"{nct_id}.json"

    def is_done(self, nct_id: str) -> bool:
        """A trial is done if its JSON exists and validates (checkpoint/resume)."""
        p = self.output_path(nct_id)
        if not p.exists():
            return False
        try:
            ClinicalTrialData.model_validate_json(p.read_text())
            return True
        except Exception:
            return False

    async def _throttle(self) -> None:
        if self.min_interval_s <= 0:
            return
        async with self._rate_lock:
            wait = self.min_interval_s - (time.time() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.time()

    async def _process_one(self, nct_id: str, extractor: Extractor, stats: RunStats) -> None:
        if self.is_done(nct_id):
            stats.skipped += 1
            return
        async with self._sem:
            await self._throttle()
            try:
                record = await extractor(nct_id)
                self.output_path(nct_id).write_text(record.model_dump_json(indent=2))
                stats.completed += 1
            except Exception as e:  # noqa: BLE001 — record and continue; one trial must not abort the run
                stats.failed += 1
                stats.errors[nct_id] = f"{type(e).__name__}: {e}"

    async def run(self, nct_ids: list[str], extractor: Extractor) -> RunStats:
        stats = RunStats(total=len(nct_ids))
        await asyncio.gather(*(self._process_one(n, extractor, stats) for n in nct_ids))
        (self.out_dir / "_run_summary.json").write_text(json.dumps(stats.summary(), indent=2))
        return stats

    def load_results(self) -> list[ClinicalTrialData]:
        """Load all validated trial JSONs from the output directory."""
        out = []
        for p in sorted(self.out_dir.glob("NCT*.json")):
            try:
                out.append(ClinicalTrialData.model_validate_json(p.read_text()))
            except Exception:
                continue
        return out

"""Tests for the parallel extraction harness: concurrency, checkpoint/resume, error isolation."""
import asyncio

import pytest

from virtual_biotech.trials.harness import ExtractionHarness
from virtual_biotech.trials.schema import ClinicalTrialData, TrialStatus


def make_record(nct_id: str) -> ClinicalTrialData:
    return ClinicalTrialData(nctId=nct_id, overallStatus=TrialStatus.RECRUITING)


@pytest.mark.asyncio
async def test_run_writes_one_json_per_trial(tmp_path):
    h = ExtractionHarness(tmp_path, concurrency=4)
    ncts = [f"NCT{i:08d}" for i in range(1, 11)]

    async def extractor(nct):
        return make_record(nct)

    stats = await h.run(ncts, extractor)
    assert stats.completed == 10 and stats.failed == 0
    assert len(list(tmp_path.glob("NCT*.json"))) == 10
    assert (tmp_path / "_run_summary.json").exists()


@pytest.mark.asyncio
async def test_resume_skips_completed(tmp_path):
    h = ExtractionHarness(tmp_path, concurrency=4)
    ncts = [f"NCT{i:08d}" for i in range(1, 6)]

    async def extractor(nct):
        return make_record(nct)

    await h.run(ncts, extractor)               # first pass: all completed

    calls = []

    async def counting_extractor(nct):
        calls.append(nct)
        return make_record(nct)

    stats = await h.run(ncts, counting_extractor)  # second pass: all skipped
    assert stats.skipped == 5
    assert calls == []                          # extractor never re-invoked


@pytest.mark.asyncio
async def test_concurrency_is_bounded(tmp_path):
    h = ExtractionHarness(tmp_path, concurrency=3)
    ncts = [f"NCT{i:08d}" for i in range(1, 13)]
    active = 0
    peak = 0

    async def extractor(nct):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return make_record(nct)

    await h.run(ncts, extractor)
    assert peak <= 3                            # semaphore respected


@pytest.mark.asyncio
async def test_one_failure_does_not_abort_run(tmp_path):
    h = ExtractionHarness(tmp_path, concurrency=4)
    ncts = [f"NCT{i:08d}" for i in range(1, 6)]

    async def extractor(nct):
        if nct == "NCT00000003":
            raise RuntimeError("boom")
        return make_record(nct)

    stats = await h.run(ncts, extractor)
    assert stats.completed == 4 and stats.failed == 1
    assert "NCT00000003" in stats.errors
    assert not h.output_path("NCT00000003").exists()


@pytest.mark.asyncio
async def test_load_results(tmp_path):
    h = ExtractionHarness(tmp_path, concurrency=2)
    ncts = ["NCT00000001", "NCT00000002"]

    async def extractor(nct):
        return make_record(nct)

    await h.run(ncts, extractor)
    loaded = h.load_results()
    assert {r.nctId for r in loaded} == set(ncts)

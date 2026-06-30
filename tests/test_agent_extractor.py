"""Tests for the live extractor's pure parts (JSON parse, target injection, cascade wiring)."""
import pytest

from virtual_biotech.trials import agent_extractor as ax
from virtual_biotech.trials.schema import EndpointResult, TrialStatus


def test_extract_json_block_from_fenced():
    text = 'Here is the result:\n```json\n{"nctId": "NCT00000001", "overallStatus": "RECRUITING"}\n```\nDone.'
    data = ax.extract_json_block(text)
    assert data["nctId"] == "NCT00000001"


def test_extract_json_block_from_bare_object():
    text = 'prefix {"a": 1, "b": {"c": 2}} suffix'
    assert ax.extract_json_block(text) == {"a": 1, "b": {"c": 2}}


def test_extract_json_block_errors_on_empty():
    with pytest.raises(ValueError):
        ax.extract_json_block("")
    with pytest.raises(ValueError):
        ax.extract_json_block("no json here")


def test_finalize_record_injects_nct_and_targets():
    data = {"overallStatus": "COMPLETED",
            "primaryEndpointResult": "POSITIVE", "secondaryEndpointResult": "NEGATIVE"}
    rec = ax.finalize_record(data, nct_id="NCT00000001", known_targets=["EGFR", "ERBB2"])
    assert rec.nctId == "NCT00000001"
    assert rec.targets == ["EGFR", "ERBB2"]
    assert rec.primaryEndpointResult is EndpointResult.POSITIVE


def test_finalize_record_keeps_agent_targets_if_present():
    data = {"nctId": "NCT00000002", "overallStatus": "RECRUITING", "targets": ["KRAS"]}
    rec = ax.finalize_record(data, nct_id="NCT00000002", known_targets=["EGFR"])
    assert rec.targets == ["KRAS"]   # agent-provided targets win


def test_build_extraction_task_mentions_targets_and_cascade():
    task = ax.build_extraction_task("NCT06137183", ["OSMR"])
    assert "NCT06137183" in task and "OSMR" in task
    assert "cascade" in task.lower() and "JSON" in task


@pytest.mark.asyncio
async def test_cascade_extractor_with_stubbed_clients():
    # Stub the registry + reasoning so no network/LLM is needed.
    async def fetch_registry(nct):
        return {"nctId": nct, "overallStatus": "TERMINATED", "phases": ["PHASE2"],
                "whyStopped": "Interim futility analysis."}

    async def reason(partial, status, ctx):
        from virtual_biotech.trials.schema import StopReasonCategory
        partial["studyStopReasonCategories"] = [StopReasonCategory.INTERIM_ANALYSIS]
        return partial

    extractor = ax.make_cascade_extractor(
        reason, cohort_targets={"NCT06137183": ["OSMR"]}, fetch_registry=fetch_registry)
    rec = await extractor("NCT06137183")
    assert rec.overallStatus is TrialStatus.TERMINATED
    assert rec.targets == ["OSMR"]                # injected from cohort
    assert rec.studyStopReason.startswith("Interim")

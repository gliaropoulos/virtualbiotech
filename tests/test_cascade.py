"""Tests for the 3-level evidence cascade logic (no LLM/network: stubs injected)."""
import pytest

from virtual_biotech.trials import cascade
from virtual_biotech.trials.schema import EndpointResult, TrialStatus

COMPLETED_SUMMARY = {
    "nctId": "NCT00000001", "title": "Done trial", "overallStatus": "COMPLETED",
    "phases": ["PHASE3"], "conditions": ["Cancer"],
}
TERMINATED_SUMMARY = {
    "nctId": "NCT06137183", "title": "Vixarelimab UC", "overallStatus": "TERMINATED",
    "phases": ["PHASE2"], "conditions": ["Ulcerative Colitis"],
    "whyStopped": "Interim futility analysis.",
}


def test_required_fields_by_status():
    assert cascade.required_fields_for_status(TrialStatus.COMPLETED) == \
        ["primaryEndpointResult", "secondaryEndpointResult"]
    assert cascade.required_fields_for_status(TrialStatus.TERMINATED) == \
        ["studyStopReason", "studyStopReasonCategories"]
    assert cascade.required_fields_for_status(TrialStatus.RECRUITING) == []


def test_missing_required_detects_empty_and_none():
    partial = {"primaryEndpointResult": None, "secondaryEndpointResult": EndpointResult.POSITIVE}
    assert cascade.missing_required(partial, TrialStatus.COMPLETED) == ["primaryEndpointResult"]


def test_prefill_from_registry_terminated_seeds_stop_reason():
    partial = cascade.prefill_from_registry(TERMINATED_SUMMARY)
    assert partial["overallStatus"] is TrialStatus.TERMINATED
    assert partial["studyStopReason"] == "Interim futility analysis."
    assert partial["dataSourceTracking"]["primarySource"] == "ClinicalTrials.gov"


def test_prefill_unknown_status_falls_back():
    partial = cascade.prefill_from_registry({"nctId": "NCT1", "overallStatus": "WEIRD"})
    assert partial["overallStatus"] is TrialStatus.UNKNOWN


@pytest.mark.asyncio
async def test_cascade_stops_at_level_1_when_registry_complete():
    async def fetch_registry(_):
        return TERMINATED_SUMMARY

    async def reason(partial, status, ctx):
        # registry already gave whyStopped; reasoner just adds the category
        from virtual_biotech.trials.schema import StopReasonCategory
        partial["studyStopReasonCategories"] = [StopReasonCategory.INTERIM_ANALYSIS]
        return partial

    record, plan = await cascade.extract_trial(
        "NCT06137183", fetch_registry=fetch_registry, reason=reason)
    assert record.overallStatus is TrialStatus.TERMINATED
    assert plan.levels_used == [1]
    assert plan.max_level == 1


@pytest.mark.asyncio
async def test_cascade_escalates_to_pubmed_then_web():
    calls = []

    async def fetch_registry(_):
        return COMPLETED_SUMMARY  # completed but no endpoint results yet

    async def fetch_pubmed(_):
        calls.append("pubmed")
        return "no result here"

    async def fetch_web(_):
        calls.append("web")
        return "press release: trial met its primary endpoint; secondary endpoints also met."

    async def reason(partial, status, ctx):
        # only the web context contains the answer
        if "met its primary endpoint" in ctx:
            partial["primaryEndpointResult"] = EndpointResult.POSITIVE
            partial["secondaryEndpointResult"] = EndpointResult.POSITIVE
        return partial

    record, plan = await cascade.extract_trial(
        "NCT00000001", fetch_registry=fetch_registry,
        fetch_pubmed=fetch_pubmed, fetch_web=fetch_web, reason=reason)
    assert record.primaryEndpointResult is EndpointResult.POSITIVE
    assert calls == ["pubmed", "web"]           # escalated through both
    assert plan.levels_used == [1, 2, 3]
    assert record.dataSourceTracking.evidenceLevelReached == 3

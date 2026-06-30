"""Tests for the ClinicalTrialData schema + status-conditional validators."""
import pytest
from pydantic import ValidationError

from virtual_biotech.trials.schema import (
    ClinicalTrialData, EndpointResult, StopReasonCategory, TrialStatus,
)


def _completed(**kw):
    base = dict(nctId="NCT00000001", overallStatus=TrialStatus.COMPLETED,
                primaryEndpointResult=EndpointResult.POSITIVE,
                secondaryEndpointResult=EndpointResult.NEGATIVE)
    base.update(kw)
    return ClinicalTrialData(**base)


def test_valid_completed_trial():
    t = _completed()
    assert t.nctId == "NCT00000001"
    assert t.primaryEndpointResult is EndpointResult.POSITIVE


def test_completed_requires_endpoint_results():
    with pytest.raises(ValidationError, match="requires"):
        ClinicalTrialData(nctId="NCT00000002", overallStatus=TrialStatus.COMPLETED)


def test_completed_unknown_allowed():
    t = _completed(primaryEndpointResult=EndpointResult.UNKNOWN,
                   secondaryEndpointResult=EndpointResult.UNKNOWN)
    assert t.primaryEndpointResult is EndpointResult.UNKNOWN


def test_terminated_requires_stop_reason_and_category():
    with pytest.raises(ValidationError, match="studyStopReason"):
        ClinicalTrialData(nctId="NCT00000003", overallStatus=TrialStatus.TERMINATED)

    with pytest.raises(ValidationError, match="1-2 studyStopReasonCategories"):
        ClinicalTrialData(nctId="NCT00000003", overallStatus=TrialStatus.TERMINATED,
                          studyStopReason="futility", studyStopReasonCategories=[])


def test_terminated_valid():
    t = ClinicalTrialData(
        nctId="NCT06137183", overallStatus=TrialStatus.TERMINATED,
        studyStopReason="Interim futility analysis suggested the primary endpoint was unlikely met.",
        studyStopReasonCategories=[StopReasonCategory.INTERIM_ANALYSIS,
                                   StopReasonCategory.NEGATIVE_LACK_OF_EFFICACY],
        targets=["OSMR"], conditions=["Ulcerative Colitis"],
    )
    assert len(t.studyStopReasonCategories) == 2
    assert t.targets == ["OSMR"]


def test_too_many_stop_categories_rejected():
    with pytest.raises(ValidationError, match="1-2"):
        ClinicalTrialData(
            nctId="NCT00000004", overallStatus=TrialStatus.TERMINATED,
            studyStopReason="x",
            studyStopReasonCategories=[StopReasonCategory.STUDY_DESIGN,
                                       StopReasonCategory.REGULATORY,
                                       StopReasonCategory.COVID_19],
        )


def test_invalid_nct_format_rejected():
    with pytest.raises(ValidationError):
        _completed(nctId="06137183")


def test_invalid_stop_category_string_rejected():
    with pytest.raises(ValidationError):
        ClinicalTrialData(nctId="NCT00000005", overallStatus=TrialStatus.TERMINATED,
                          studyStopReason="x", studyStopReasonCategories=["Made up reason"])


def test_recruiting_trial_needs_neither():
    t = ClinicalTrialData(nctId="NCT00000006", overallStatus=TrialStatus.RECRUITING)
    assert t.primaryEndpointResult is None
    assert t.studyStopReasonCategories == []


def test_sixteen_stop_categories_defined():
    assert len(list(StopReasonCategory)) == 16


def test_roundtrip_json():
    t = _completed(targets=["EGFR"])
    restored = ClinicalTrialData.model_validate_json(t.model_dump_json())
    assert restored == t

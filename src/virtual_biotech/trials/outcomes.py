"""Derive the binary/continuous trial outcomes analyzed in the paper from ClinicalTrialData.

Outcomes:
* endpoint_success  — primary endpoint POSITIVE(1)/NEGATIVE(0); None if UNKNOWN.
* terminated_for_efficacy — among stopped trials, 1 if stopped for lack of efficacy.
* serious_ae_rate   — continuous [0,1] from the adverse-event profile (for beta regression).

These are pure functions over a validated record so they are unit-testable.
"""
from __future__ import annotations

from .schema import (
    STOPPED_STATUSES, ClinicalTrialData, EndpointResult, StopReasonCategory,
)


def endpoint_success(t: ClinicalTrialData) -> int | None:
    """1 if the primary endpoint was met, 0 if not, None if unknown/not applicable."""
    r = t.primaryEndpointResult
    if r is EndpointResult.POSITIVE:
        return 1
    if r is EndpointResult.NEGATIVE:
        return 0
    return None


def terminated_for_efficacy(t: ClinicalTrialData) -> int | None:
    """Among stopped trials: 1 if a stop-reason category is lack of efficacy, else 0. None otherwise."""
    if t.overallStatus not in STOPPED_STATUSES:
        return None
    return int(StopReasonCategory.NEGATIVE_LACK_OF_EFFICACY in t.studyStopReasonCategories)


def serious_ae_rate(t: ClinicalTrialData) -> float | None:
    """Serious AE rate in [0,1], preferring an explicit rate, else count/participants."""
    ae = t.adverseEventProfile
    if ae is None:
        return None
    if ae.seriousAeRate is not None:
        return max(0.0, min(1.0, ae.seriousAeRate))
    if ae.seriousEventCount is not None and ae.totalParticipants:
        return max(0.0, min(1.0, ae.seriousEventCount / ae.totalParticipants))
    return None


# Registry of named outcome extractors for the pipeline.
OUTCOMES = {
    "endpoint_success": endpoint_success,
    "terminated_for_efficacy": terminated_for_efficacy,
    "serious_ae_rate": serious_ae_rate,
}

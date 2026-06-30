"""`ClinicalTrialData` — the validated output schema for trial-outcome extraction.

Ported from the clinical trialist agent's spec (Supplementary Note I of Zhang et al. 2026):
status-conditional required fields enforced by a Pydantic `@model_validator`, the 16-category
controlled vocabulary for stop reasons, POSITIVE/NEGATIVE/UNKNOWN endpoint results, and
data-source provenance tracking. Each extraction agent writes one `{nct_id}.json` validated against
this schema; on failure it returns to its evidence sources and re-validates until passing.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TrialStatus(str, Enum):
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    SUSPENDED = "SUSPENDED"
    WITHDRAWN = "WITHDRAWN"
    RECRUITING = "RECRUITING"
    ACTIVE_NOT_RECRUITING = "ACTIVE_NOT_RECRUITING"
    NOT_YET_RECRUITING = "NOT_YET_RECRUITING"
    ENROLLING_BY_INVITATION = "ENROLLING_BY_INVITATION"
    UNKNOWN = "UNKNOWN"


# Statuses that require endpoint results vs. those that require a stop reason.
COMPLETED_STATUSES = {TrialStatus.COMPLETED}
STOPPED_STATUSES = {TrialStatus.TERMINATED, TrialStatus.SUSPENDED, TrialStatus.WITHDRAWN}


class EndpointResult(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    UNKNOWN = "UNKNOWN"


class StopReasonCategory(str, Enum):
    """The 16 valid stop-reason categories (copy strings exactly)."""
    INSUFFICIENT_ENROLLMENT = "Insufficient enrollment"
    BUSINESS_OR_ADMINISTRATIVE = "Business or administrative"
    NEGATIVE_LACK_OF_EFFICACY = "Negative (lack of efficacy)"
    STUDY_DESIGN = "Study design"
    INVALID_REASON = "Invalid reason"
    SAFETY_OR_SIDE_EFFECTS = "Safety or side effects"
    LOGISTICS_OR_RESOURCES = "Logistics or resources"
    ANOTHER_STUDY = "Another study"
    STUDY_STAFF_MOVED = "Study staff moved"
    REGULATORY = "Regulatory"
    NO_CONTEXT = "No context"
    COVID_19 = "COVID-19"
    UNCATEGORISED = "Uncategorised"
    INTERIM_ANALYSIS = "Interim analysis"
    INSUFFICIENT_DATA = "Insufficient data"
    SUCCESS = "Success"


class AdverseEventProfile(BaseModel):
    seriousEventCount: int | None = None
    otherEventCount: int | None = None
    totalParticipants: int | None = None
    seriousAeRate: float | None = Field(default=None, description="serious AEs / participants, [0,1]")
    notes: str | None = None


class DataSourceTracking(BaseModel):
    """Provenance: which source provided which field (paper requires this be populated)."""
    primarySource: str | None = None          # e.g. "ClinicalTrials.gov"
    resultsSource: str | None = None
    adverseEventsSource: str | None = None
    additionalSourcesUsed: list[str] = Field(default_factory=list)
    pubmedIds: list[str] = Field(default_factory=list)
    webUrls: list[str] = Field(default_factory=list)
    evidenceLevelReached: int | None = Field(default=None, ge=1, le=3)


class ClinicalTrialData(BaseModel):
    """Structured, validated record for one clinical trial."""
    nctId: str = Field(pattern=r"^NCT\d{8}$")
    title: str | None = None
    overallStatus: TrialStatus
    phase: str | None = None
    targets: list[str] = Field(default_factory=list, description="HGNC symbols of molecular targets")
    conditions: list[str] = Field(default_factory=list)

    # COMPLETED-required
    primaryEndpointResult: EndpointResult | None = None
    secondaryEndpointResult: EndpointResult | None = None
    primaryEndpointNotes: str | None = None
    secondaryEndpointNotes: str | None = None

    # TERMINATED/SUSPENDED/WITHDRAWN-required
    studyStopReason: str | None = None
    studyStopReasonCategories: list[StopReasonCategory] = Field(default_factory=list)

    adverseEventProfile: AdverseEventProfile | None = None
    dataSourceTracking: DataSourceTracking = Field(default_factory=DataSourceTracking)

    @model_validator(mode="after")
    def _status_conditional_requirements(self) -> "ClinicalTrialData":
        status = self.overallStatus
        if status in COMPLETED_STATUSES:
            missing = [f for f in ("primaryEndpointResult", "secondaryEndpointResult")
                       if getattr(self, f) is None]
            if missing:
                raise ValueError(
                    f"COMPLETED trial {self.nctId} requires {missing} "
                    f"(use EndpointResult.UNKNOWN only after exhausting all 3 evidence levels)."
                )
        if status in STOPPED_STATUSES:
            if not self.studyStopReason:
                raise ValueError(f"{status.value} trial {self.nctId} requires studyStopReason.")
            n = len(self.studyStopReasonCategories)
            if not (1 <= n <= 2):
                raise ValueError(
                    f"{status.value} trial {self.nctId} requires 1-2 studyStopReasonCategories "
                    f"(got {n}). Use ['No context'] if unclear."
                )
        return self

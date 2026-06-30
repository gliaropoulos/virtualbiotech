"""The clinical trialist's 3-level evidence cascade as explicit, testable control logic.

Level 1: ClinicalTrials.gov API (always first)
Level 2: PubMed (if required fields still missing) — with NCT-ID verification
Level 3: other web sources (press releases, FDA, news) — NCT-ID verification still required

The *decisions* (what's required, whether to escalate, prefill from the registry record) are pure
functions here. The agentic reasoning that fills the remaining fields from fetched text is injected
as a callable, so this module is fully unit-testable without an LLM or network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .schema import (
    COMPLETED_STATUSES, STOPPED_STATUSES, ClinicalTrialData, DataSourceTracking, TrialStatus,
)


def required_fields_for_status(status: TrialStatus) -> list[str]:
    """Which fields must be populated for this trial status (paper's rules)."""
    if status in COMPLETED_STATUSES:
        return ["primaryEndpointResult", "secondaryEndpointResult"]
    if status in STOPPED_STATUSES:
        return ["studyStopReason", "studyStopReasonCategories"]
    return []  # active/recruiting trials have no required outcome fields


def missing_required(partial: dict, status: TrialStatus) -> list[str]:
    """Return required fields that are still absent/empty in a partial extraction dict."""
    out = []
    for f in required_fields_for_status(status):
        val = partial.get(f)
        if val is None or (isinstance(val, (list, str)) and len(val) == 0):
            out.append(f)
    return out


def is_complete(partial: dict, status: TrialStatus) -> bool:
    return not missing_required(partial, status)


def prefill_from_registry(summary: dict) -> dict:
    """Seed a partial record from the ClinicalTrials.gov summary (the level-1 source).

    `summary` is the output of mcp_servers.clinicaltrials.client.summarize_study.
    """
    status_raw = (summary.get("overallStatus") or "UNKNOWN").upper()
    try:
        status = TrialStatus(status_raw)
    except ValueError:
        status = TrialStatus.UNKNOWN
    partial = {
        "nctId": summary.get("nctId"),
        "title": summary.get("title"),
        "overallStatus": status,
        "phase": ",".join(summary.get("phases") or []) or None,
        "conditions": summary.get("conditions") or [],
        "dataSourceTracking": {"primarySource": "ClinicalTrials.gov", "evidenceLevelReached": 1},
    }
    # The registry's whyStopped seeds the stop reason for terminated trials.
    if status in STOPPED_STATUSES and summary.get("whyStopped"):
        partial["studyStopReason"] = summary["whyStopped"]
    return partial


@dataclass
class CascadeStep:
    level: int
    name: str
    used: bool = False
    note: str = ""


@dataclass
class ExtractionPlan:
    """Records which cascade levels were needed — the audit trail for one trial."""
    nct_id: str
    steps: list[CascadeStep] = field(default_factory=lambda: [
        CascadeStep(1, "ClinicalTrials.gov"),
        CascadeStep(2, "PubMed"),
        CascadeStep(3, "Web sources"),
    ])

    def mark(self, level: int, note: str = "") -> None:
        self.steps[level - 1].used = True
        if note:
            self.steps[level - 1].note = note

    @property
    def levels_used(self) -> list[int]:
        return [s.level for s in self.steps if s.used]

    @property
    def max_level(self) -> int:
        return max(self.levels_used, default=1)


# A reasoning step takes (partial, status, fetched_context) and returns an updated partial.
ReasoningFn = Callable[[dict, TrialStatus, str], Awaitable[dict]]


async def extract_trial(
    nct_id: str,
    *,
    fetch_registry: Callable[[str], Awaitable[dict]],
    fetch_pubmed: Callable[[str], Awaitable[str]] | None = None,
    fetch_web: Callable[[str], Awaitable[str]] | None = None,
    reason: ReasoningFn | None = None,
) -> tuple[ClinicalTrialData, ExtractionPlan]:
    """Run the 3-level cascade for one NCT ID and return a validated record + audit plan.

    The fetch_* and reason callables are injected: in production they wrap the clinicaltrials/pubmed
    MCP tools and the agent's LLM; in tests they are simple stubs. Escalation stops as soon as the
    status-required fields are populated.
    """
    plan = ExtractionPlan(nct_id)

    # Level 1 — registry (always)
    summary = await fetch_registry(nct_id)
    partial = prefill_from_registry(summary)
    status = partial["overallStatus"]
    plan.mark(1)
    if reason:
        partial = await reason(partial, status, _registry_context(summary))

    # Level 2 — PubMed
    if not is_complete(partial, status) and fetch_pubmed and reason:
        context = await fetch_pubmed(nct_id)
        partial = await reason(partial, status, context)
        partial.setdefault("dataSourceTracking", {})["evidenceLevelReached"] = 2
        plan.mark(2, "required fields missing after registry")

    # Level 3 — web
    if not is_complete(partial, status) and fetch_web and reason:
        context = await fetch_web(nct_id)
        partial = await reason(partial, status, context)
        partial.setdefault("dataSourceTracking", {})["evidenceLevelReached"] = 3
        plan.mark(3, "required fields missing after PubMed")

    record = ClinicalTrialData.model_validate(partial)
    return record, plan


def _registry_context(summary: dict) -> str:
    parts = [f"{k}: {v}" for k, v in summary.items() if v]
    return "\n".join(parts)

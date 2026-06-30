"""Live clinical-trialist extractor: turns an NCT ID into a validated ClinicalTrialData record.

Two extractor builders, both producing an async `nct_id -> ClinicalTrialData` callable suitable for
the parallel ExtractionHarness:

* `make_agent_extractor` — the paper's approach: a dedicated clinical-trialist agent (Claude Agent
  SDK, Sonnet) per trial, given the clinicaltrials + pubmed MCP tools and instructed to follow the
  3-level evidence cascade and emit JSON matching the schema. Requires the SDK + an API key.

* `make_cascade_extractor` — the deterministic cascade (trials.cascade) wired to the real
  ClinicalTrials.gov / PubMed clients, with the per-field reasoning step injected. Cheaper and fully
  controllable; the reasoning callable can be an LLM or, in tests, a stub.

The JSON parsing, target injection, and validation are pure functions and are unit-tested; only the
actual agent/network calls are gated behind the SDK/key/clients.
"""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from .schema import ClinicalTrialData

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_block(text: str) -> dict:
    """Pull the JSON object out of an agent's free-text response (handles ```json fences)."""
    if not text or not text.strip():
        raise ValueError("empty agent response")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        m = _JSON_BLOCK.search(text)
        if not m:
            raise ValueError("no JSON object found in agent response")
        candidate = m.group(0)
    return json.loads(candidate)


def finalize_record(data: dict, *, nct_id: str, known_targets: list[str] | None = None
                    ) -> ClinicalTrialData:
    """Inject the NCT ID and Open Targets-derived targets, then validate against the schema.

    The cohort's target mapping comes from Open Targets (which already maps trials to molecular
    targets); the agent supplies the outcome annotations. We trust the cohort for `targets` unless
    the agent already provided them.
    """
    data = dict(data)
    data.setdefault("nctId", nct_id)
    if known_targets and not data.get("targets"):
        data["targets"] = list(known_targets)
    return ClinicalTrialData.model_validate(data)


def build_extraction_task(nct_id: str, known_targets: list[str] | None) -> str:
    """The instruction handed to a per-trial clinical-trialist agent."""
    tgt = f" Known molecular target(s) from Open Targets: {', '.join(known_targets)}." if known_targets else ""
    return (
        f"Extract structured outcome data for clinical trial {nct_id}.{tgt}\n"
        "Follow the 3-level evidence cascade (ClinicalTrials.gov, then PubMed, then web) and your "
        "system prompt's rules for required fields by trial status. Return ONLY a single JSON object "
        "matching the ClinicalTrialData schema (nctId, overallStatus, and the status-required "
        "fields), with dataSourceTracking populated. Do not include any prose outside the JSON."
    )


# Reasoning callable used by the cascade extractor: (partial, status, context) -> updated partial.
ReasoningFn = Callable[[dict, object, str], Awaitable[dict]]


def make_agent_extractor(cohort_targets: dict[str, list[str]] | None = None,
                         *, agent_key: str = "clinical_trialist"):
    """Build an extractor backed by a per-trial clinical-trialist agent (Agent SDK + API key)."""
    from ..agents.base import BaseAgent

    agent = BaseAgent.from_key(agent_key)

    async def extractor(nct_id: str) -> ClinicalTrialData:
        known = (cohort_targets or {}).get(nct_id)
        task = build_extraction_task(nct_id, known)
        output = await agent.run(task)               # requires SDK + ANTHROPIC_API_KEY
        return finalize_record(extract_json_block(output), nct_id=nct_id, known_targets=known)

    return extractor


def make_cascade_extractor(reason: ReasoningFn,
                           *, cohort_targets: dict[str, list[str]] | None = None,
                           fetch_registry=None, fetch_pubmed=None, fetch_web=None):
    """Build an extractor using the deterministic cascade + real data clients + injected reasoning.

    Defaults wire `fetch_registry`/`fetch_pubmed` to the ClinicalTrials.gov / PubMed MCP clients.
    """
    from . import cascade

    if fetch_registry is None:
        fetch_registry = _default_registry_fetch
    if fetch_pubmed is None:
        fetch_pubmed = _default_pubmed_fetch

    async def extractor(nct_id: str) -> ClinicalTrialData:
        record, _plan = await cascade.extract_trial(
            nct_id, fetch_registry=fetch_registry, fetch_pubmed=fetch_pubmed,
            fetch_web=fetch_web, reason=reason)
        known = (cohort_targets or {}).get(nct_id)
        if known and not record.targets:
            record = record.model_copy(update={"targets": list(known)})
        return record

    return extractor


async def _default_registry_fetch(nct_id: str) -> dict:
    """Level-1 fetch via the ClinicalTrials.gov client -> the summary dict the cascade expects."""
    from mcp_servers.clinicaltrials import client as ct
    return ct.summarize_study(await ct.fetch_study(nct_id))


async def _default_pubmed_fetch(nct_id: str) -> str:
    """Level-2 context: concatenated abstracts of PubMed hits for the NCT ID (verified)."""
    from mcp_servers.pubmed import client as pm
    pmids = pm.parse_pmids(await pm.esearch(nct_id, retmax=3))
    chunks = []
    for pmid in pmids:
        text = await pm.efetch_abstract(pmid)
        if pm.verify_nct(text, nct_id):
            chunks.append(text)
    return "\n\n".join(chunks)

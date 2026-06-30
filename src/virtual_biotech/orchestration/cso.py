"""CSO orchestration skeleton.

Implements the control flow from Figure 1C of the paper:

    clarify (+ chief-of-staff briefing) -> decompose -> route to scientists
        -> scientific review -> (re-delegate on gaps) -> synthesize

This module wires the *structure*. The actual model calls run through `BaseAgent.run`, which
requires the Claude Agent SDK + an API key. Without those, the orchestrator can still be exercised
in a dry-run mode that records the plan and routing decisions to the session workspace — useful for
testing the topology before incurring cost.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..agents.base import BaseAgent
from ..agents.registry import REGISTRY, scientists
from ..common.workspace import Session


@dataclass
class SubTask:
    agent_key: str
    instruction: str
    result: str | None = None


@dataclass
class CSO:
    """Chief Scientific Officer orchestrator."""

    session: Session
    dry_run: bool = True  # if True, record plan without calling models

    agent: BaseAgent = field(init=False)

    def __post_init__(self) -> None:
        self.agent = BaseAgent.from_key("cso")

    # --- phase 1: orientation -------------------------------------------------------------
    async def brief(self, query: str) -> str:
        """Chief of Staff briefing on field/data landscape (parallelizable with clarification)."""
        cos = BaseAgent.from_key("chief_of_staff")
        self.session.log("brief.request", {"query": query})
        if self.dry_run:
            return f"[dry-run briefing for: {query}]"
        return await cos.run(f"Prepare a briefing for this query:\n{query}",
                             workspace=str(self.session.dir))

    def clarification_questions(self, query: str) -> list[str]:
        """Stub: in full mode the CSO model generates these. Here we record the intent."""
        self.session.log("clarify.intent", {"query": query})
        return []

    # --- phase 2: decomposition + routing -------------------------------------------------
    def decompose(self, query: str) -> list[SubTask]:
        """Route a query to relevant scientists.

        Placeholder routing: the production CSO uses the model to choose agents and write
        per-agent instructions. Here we expose the topology and a trivial keyword router so the
        flow is testable. Replace with model-driven routing in Phase 2c.
        """
        chosen = _keyword_route(query)
        tasks = [SubTask(k, f"Analyze the following for your domain:\n{query}") for k in chosen]
        self.session.log("decompose", {"agents": [t.agent_key for t in tasks]})
        return tasks

    async def dispatch(self, tasks: Iterable[SubTask]) -> list[SubTask]:
        out: list[SubTask] = []
        for t in tasks:
            agent = BaseAgent.from_key(t.agent_key)
            self.session.log("dispatch", {"agent": t.agent_key})
            t.result = (
                f"[dry-run result from {t.agent_key}]"
                if self.dry_run
                else await agent.run(t.instruction, workspace=str(self.session.dir))
            )
            out.append(t)
        return out

    # --- phase 3: review + synthesis ------------------------------------------------------
    async def review(self, tasks: list[SubTask]) -> str:
        reviewer = BaseAgent.from_key("scientific_reviewer")
        payload = "\n\n".join(f"## {t.agent_key}\n{t.result}" for t in tasks)
        self.session.log("review.request", {"n_outputs": len(tasks)})
        if self.dry_run:
            return "[dry-run review: APPROVE]"
        return await reviewer.run(f"Review these scientist outputs:\n{payload}",
                                  workspace=str(self.session.dir))

    async def synthesize(self, query: str, tasks: list[SubTask], review: str) -> str:
        self.session.log("synthesize", {"query": query})
        if self.dry_run:
            agents = ", ".join(t.agent_key for t in tasks)
            return f"[dry-run synthesis for '{query}' using: {agents}]"
        body = "\n\n".join(f"{t.agent_key}: {t.result}" for t in tasks)
        return await self.agent.run(
            f"User query: {query}\n\nScientist findings:\n{body}\n\nReviewer:\n{review}\n\n"
            "Synthesize a final, data-driven recommendation.",
            workspace=str(self.session.dir),
        )

    # --- top-level entrypoint -------------------------------------------------------------
    async def handle(self, query: str) -> str:
        await self.brief(query)
        self.clarification_questions(query)
        tasks = await self.dispatch(self.decompose(query))
        review = await self.review(tasks)
        report = await self.synthesize(query, tasks, review)
        self.session.log("report", {"chars": len(report)})
        return report


def _keyword_route(query: str) -> list[str]:
    """Minimal placeholder router (Phase 2c replaces this with model-driven routing)."""
    q = query.lower()
    chosen: list[str] = []
    rules = {
        "statistical_genetics": ("genetic", "gwas", "variant", "heritab"),
        "single_cell_atlas": ("single cell", "single-cell", "expression", "cell type", "atlas"),
        "functional_genomics": ("essential", "crispr", "perturbation", "dependency"),
        "bio_pathways": ("pathway", "interaction", "signaling", "network"),
        "fda_safety_officer": ("safety", "adverse", "toxicity", "black box"),
        "target_biologist": ("modality", "structure", "tractab", "antibody", "small molecule"),
        "pharmacologist": ("drug", "chembl", "precedent", "mechanism of action"),
        "clinical_trialist": ("trial", "clinical", "endpoint", "phase", "nct"),
    }
    for key, kws in rules.items():
        if any(kw in q for kw in kws):
            chosen.append(key)
    return chosen or ["statistical_genetics", "clinical_trialist"]  # sensible default

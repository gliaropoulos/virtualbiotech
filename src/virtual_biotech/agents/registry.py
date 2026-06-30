"""The Virtual Biotech org chart: 11 agents, their models, divisions, and MCP permissions.

This is the single source of truth for *who* exists and *what data each agent may touch*
(separation of responsibilities). The orchestration layer reads this to spawn agents with the
correct system prompt and tool access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .. import config


class Division(str, Enum):
    OFFICE_OF_CSO = "Office of the CSO"
    TARGET_ID = "Target Identification & Prioritization"
    TARGET_SAFETY = "Target Safety"
    MODALITY = "Modality Selection"
    CLINICAL = "Clinical Officers"


@dataclass(frozen=True)
class AgentSpec:
    key: str                      # stable id, matches prompt file stem
    name: str                     # human-readable
    division: Division
    model: str                    # resolved at construction from config
    mcp_servers: tuple[str, ...]  # which FastMCP servers this agent may use
    prompt: str                   # prompt file stem (defaults to key)
    description: str = ""

    @property
    def prompt_name(self) -> str:
        return self.prompt or self.key


_S = config.MODEL_SCIENTIST
_O = config.MODEL_ORCHESTRATOR
_H = config.MODEL_SUPPORT

# Standard compute tools (file ops + code execution) are granted to every scientist by the
# orchestration layer; only domain-specific MCP servers are listed here.
REGISTRY: dict[str, AgentSpec] = {a.key: a for a in [
    # --- Office of the CSO -----------------------------------------------------------------
    AgentSpec("cso", "CSO Orchestrator", Division.OFFICE_OF_CSO, _O, (),
              "cso", "Interprets queries, decomposes, routes, synthesizes. Never analyzes data."),
    AgentSpec("chief_of_staff", "Chief of Staff", Division.OFFICE_OF_CSO, _H, ("pubmed",),
              "chief_of_staff", "Field/data-landscape briefings via MCP inventory + web search."),
    AgentSpec("scientific_reviewer", "Scientific Reviewer", Division.OFFICE_OF_CSO, _H, (),
              "scientific_reviewer", "QA of scientist outputs: relevance, evidence strength, rigor."),

    # --- Target Identification & Prioritization -------------------------------------------
    AgentSpec("statistical_genetics", "Statistical Genetics Agent", Division.TARGET_ID, _S,
              ("open_targets", "gnomad"), "statistical_genetics",
              "GWAS, L2G, fine-mapped credible sets, rare-variant burden, QTL colocalization."),
    AgentSpec("functional_genomics", "Functional Genomics & Perturbation Agent", Division.TARGET_ID,
              _S, ("depmap", "tahoe", "open_targets"), "functional_genomics",
              "CRISPR essentiality + drug-perturbation transcriptomics (Tahoe-100M)."),
    AgentSpec("single_cell_atlas", "Single-Cell Atlas Agent", Division.TARGET_ID, _S,
              ("cellxgene", "tabula_sapiens"), "single_cell_atlas",
              "Cell-type expression, disease-vs-healthy DE, cell-cell communication."),

    # --- Target Safety --------------------------------------------------------------------
    AgentSpec("bio_pathways", "Bio-Pathways & PPI Agent", Division.TARGET_SAFETY, _S,
              ("open_targets",), "bio_pathways",
              "Pathway + protein-interaction reasoning for collateral safety effects."),
    AgentSpec("fda_safety_officer", "FDA Safety Officer Agent", Division.TARGET_SAFETY, _S,
              ("openfda", "dailymed", "open_targets"), "fda_safety_officer",
              "OpenFDA adverse events, drug labels/black-box, mouse KO phenotypes."),

    # --- Modality Selection ---------------------------------------------------------------
    AgentSpec("target_biologist", "Target Biologist Agent", Division.MODALITY, _S,
              ("open_targets",), "target_biologist",
              "Protein family, localization, structural tractability, modality feasibility."),
    AgentSpec("pharmacologist", "Pharmacologist Agent", Division.MODALITY, _S,
              ("open_targets",), "pharmacologist",
              "ChEMBL drugs/MoA, chemical probes, clinical precedence, homolog tractability."),

    # --- Clinical Officers ----------------------------------------------------------------
    AgentSpec("clinical_trialist", "Clinical Trialist Agent", Division.CLINICAL, _S,
              ("clinicaltrials", "pubmed", "cbioportal"), "clinical_trialist",
              "Trial outcome extraction; clinical precedence; oncology clinicogenomics."),
]}

# The single-cell atlas agent and FDA safety officer are shared across divisions in the paper.
# We model them once and let the relevant divisions reference them.
SHARED_ACROSS_DIVISIONS = {
    "single_cell_atlas": (Division.TARGET_ID, Division.TARGET_SAFETY),
    "fda_safety_officer": (Division.TARGET_SAFETY, Division.CLINICAL),
}

DIVISIONS: dict[Division, list[str]] = {}
for spec in REGISTRY.values():
    DIVISIONS.setdefault(spec.division, []).append(spec.key)
for key, divs in SHARED_ACROSS_DIVISIONS.items():
    for d in divs:
        if key not in DIVISIONS.setdefault(d, []):
            DIVISIONS[d].append(key)


def scientists() -> list[AgentSpec]:
    """All domain scientist agents (everything outside the Office of the CSO)."""
    return [s for s in REGISTRY.values() if s.division is not Division.OFFICE_OF_CSO]


def get(key: str) -> AgentSpec:
    return REGISTRY[key]

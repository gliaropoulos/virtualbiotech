# Virtual Biotech — Development Plan

A faithful, reusable re-implementation of **"The Virtual Biotech: A Multi-Agent AI Framework
for Therapeutic Discovery and Development"** (Zhang et al., bioRxiv 2026,
doi:10.64898/2026.02.23.707551).

This document is the master plan. It defines the target architecture, the build phases, and the
acceptance criteria for each phase. It is written so that work can proceed incrementally — each
phase produces something runnable.

---

## 1. Goal and guiding principles

**Goal.** Recreate the full Virtual Biotech: a hierarchical multi-agent system that emulates a
therapeutics R&D organization, with a CSO orchestrator coordinating eight specialized scientist
agents across four divisions, plus three "office of the CSO" agents, all backed by ~10 FastMCP
servers exposing 100+ tools over public biomedical databases. Reproduce the three case studies
end to end.

**Principles.**

1. **Match the paper's stack.** Python, the **Claude Agent SDK** for orchestration and
   sub-agent spawning, and **FastMCP** for the data tool layer. Claude Sonnet 4.5 for scientist
   agents; Claude Haiku 4.5 for the Chief of Staff and Scientific Reviewer.
2. **Separation of concerns.** The CSO orchestrates and never touches data. Scientist agents own
   domain analysis. MCP servers own data access. Analysis libraries own statistics. The UI owns
   presentation. These layers must stay decoupled.
3. **Composable, typed tools.** Every MCP tool is a Python function with typed parameters and a
   rich docstring; FastMCP introspects these into schemas. Tools return both raw data and
   LLM-friendly summaries/previews.
4. **Auditability.** Every session writes a reproducible workspace: the reasoning trace, the
   tool calls, the generated code, the figures, and the data. A human expert should be able to
   re-run any result.
5. **Build first, wire keys later.** All code is written so it runs once an Anthropic API key and
   data credentials are supplied. Nothing in the scaffold hard-requires secrets to import or test.
6. **Incremental and testable.** Each phase ends with something that runs and has tests. We do not
   move on until the current layer is green.

---

## 2. Target architecture

```
                          ┌─────────────────────────────┐
            Human user ──▶│   CSO Orchestrator (Sonnet)  │  clarify → decompose → route → synthesize
                          └──────────────┬──────────────┘
                  ┌──────────────────────┼───────────────────────┐
        ┌─────────▼────────┐   ┌─────────▼────────┐    ┌──────────▼─────────┐
        │  Chief of Staff   │   │ Scientific Review │    │  Scientist agents  │
        │   (Haiku)         │   │   (Haiku)         │    │  (Sonnet, 4 divs)  │
        │ field briefing    │   │ QA / gap-finding  │    └──────────┬─────────┘
        └───────────────────┘   └───────────────────┘               │
                                                       ┌────────────┴────────────┐
                                                       │   MCP tool layer        │
                                                       │  (~10 FastMCP servers)  │
                                                       └────────────┬────────────┘
                                                       Open Targets, ClinicalTrials.gov, PubMed,
                                                       CELLxGENE, Tabula Sapiens, Tahoe-100M,
                                                       cBioPortal, OpenFDA, DailyMed, gnomAD/ClinVar,
                                                       DepMap, ...
```

### 2.1 Agents (11 total)

**Office of the CSO**

| Agent | Model | Role |
|---|---|---|
| CSO Orchestrator | Sonnet 4.5 | Interprets queries, clarifies intent, decomposes tasks, routes to scientists, synthesizes. Never analyzes data directly. |
| Chief of Staff | Haiku 4.5 | Strategic intelligence briefings: field awareness, data landscape, recent developments. Inventories MCP tools + web search. |
| Scientific Reviewer | Haiku 4.5 | QA of scientist outputs against 3 criteria: addresses the question, evidence strength, thoroughness. Issues revision requests. |

**Division 1 — Target Identification & Prioritization**

| Agent | Tools / data |
|---|---|
| Statistical Genetics agent | GWAS, L2G predictions, fine-mapped credible sets, rare-variant burden, QTL colocalization (Open Targets, gnomAD, ClinVar) |
| Functional Genomics & Perturbation agent | CRISPR essentiality (DepMap), drug-perturbation transcriptomics (Tahoe-100M) |
| Single-Cell Atlas agent | Cell-type-specific expression, disease-vs-healthy DE, cell-cell communication (CELLxGENE Census, Tabula Sapiens v2) |

**Division 2 — Target Safety**

| Agent | Tools / data |
|---|---|
| Bio-Pathways & PPI agent | Pathway/interaction maps, collateral-effect reasoning |
| Single-Cell Atlas agent (shared) | Off-target toxicity via cell-type expression across 27 Tabula Sapiens tissues |
| FDA Safety Officer agent | OpenFDA adverse events, drug labels/black-box (DailyMed), mouse KO phenotypes |

**Division 3 — Modality Selection**

| Agent | Tools / data |
|---|---|
| Target Biologist agent | Protein family, localization, structural tractability, modality feasibility |
| Pharmacologist agent | ChEMBL drugs/MoA, chemical probes, clinical precedence, homolog tractability |

**Division 4 — Clinical Officers**

| Agent | Tools / data |
|---|---|
| Clinical Trialist agent | ClinicalTrials.gov, PubMed, web; trial outcome extraction; cBioPortal clinicogenomics for oncology |
| FDA Safety Officer agent (shared) | Regulatory safety precedence |

### 2.2 MCP servers (target list, ~10)

1. **open_targets** — GraphQL backbone (v25.09): targets, diseases, GWAS, L2G, credible sets,
   QTL colocalization, ChEMBL drugs/MoA, drug labels, FDA signals, clinical trials, tractability.
2. **clinicaltrials** — ClinicalTrials.gov v2 API: trial details, status, eligibility, outcomes,
   whyStopped, posted adverse events.
3. **pubmed** — NCBI E-utilities: search + fetch, NCT-ID verification.
4. **cellxgene** — CELLxGENE Census API: cell-type expression, DE, marker genes.
5. **tabula_sapiens** — local Tabula Sapiens v2 atlas: tau specificity, bimodality, per-tissue
   expression.
6. **tahoe** — Tahoe-100M perturbation profiles: hallmark signature scores.
7. **cbioportal** — cBioPortal REST: clinicogenomics, survival, biomarker stratification.
8. **openfda** — OpenFDA drug adverse-event reports.
9. **dailymed** — DailyMed drug labels / black-box warnings.
10. **gnomad** — gnomAD + ClinVar variant constraint / pLoF / pathogenicity.
11. *(stretch)* **depmap** — DepMap CRISPR essentiality (could also live in open_targets).

### 2.3 Analysis layer (reusable scientific code)

Pure-Python (statsmodels) libraries the agents call via skills/code execution. The paper used R for
beta regression and the mixed-effects GLMMs; we replace those with native statsmodels equivalents
(`BetaModel`, `BinomialBayesMixedGLM`) so the whole stack is Python-only — no R / rpy2:

- **trial_outcomes/** — Pydantic `ClinicalTrialData` schema; parallel extraction harness;
  single-cell feature engineering (tau index, bimodality coefficient, Tahoe hallmark scores);
  logistic / beta regression; permutation tests; GLMM confounder adjustment — all via statsmodels
  (`GLM` Binomial, `BetaModel`, `BinomialBayesMixedGLM`).
- **sc_spatial/** — Scanpy QC pipeline, Harmony integration, PyDESeq2 pseudobulk DE, LIANA
  cell-cell communication, Cell2Location spatial deconvolution, PROGENy pathway activity
  (decoupler).
- **b7h3_luad/** — spatial immune-neighborhood mixed models; TCGA LUAD biomarker-stratified Cox
  survival (lifelines).
- **osmr_uc/** — cross-trial GEO baseline-expression comparison; OSMR gradient mixed-effects
  program; PROGENy JAK-STAT dynamics.

### 2.4 UI

A chat interface showing live agent reasoning, which tools are running, and a per-session isolated
workspace with downloadable code/figures/data (paper Figure S1).

---

## 3. Build phases

Each phase is independently shippable. Estimated effort assumes one engineer + this agent pair.

### Phase 0 — Repository scaffold ✅ (this session)
- Package layout, `pyproject.toml`, `.env.example`, `.gitignore`, README, ARCHITECTURE doc.
- Config module (model routing, paths, credential loading).
- CI stub + test harness.
- **Done when:** `pip install -e .` works and `pytest` passes on the smoke tests.

### Phase 1 — MCP tool layer (the data foundation)
The agents are useless without tools, so this comes first.
- **1a.** Reference server: **clinicaltrials** (no auth, central to case study 1). Establishes the
  FastMCP pattern: typed tools, docstrings, raw+summary returns, a local test client.
- **1b.** **pubmed** + **openfda** + **dailymed** (public, no/low auth).
- **1c.** **open_targets** GraphQL (largest; many tools — genetics, drugs, trials, tractability).
- **1d.** **cbioportal**, **gnomad**.
- **1e.** Data-heavy local/remote: **cellxgene**, **tabula_sapiens**, **tahoe**, **depmap**
  (require dataset downloads; gated behind a data-setup script).
- **Done when:** each server starts, lists its tools, and returns live data for a smoke query;
  a shared MCP test client exercises every tool.

### Phase 2 — Agent + orchestration framework
- **2a.** `BaseAgent` over the Claude Agent SDK: system prompt, model, allowed MCP servers,
  workspace, structured logging of reasoning + tool calls.
- **2b.** Agent registry + division config (which agent gets which MCP servers).
- **2c.** CSO Orchestrator: clarification interview, task decomposition, routing (parallel and
  sequential), synthesis. Chief of Staff briefing. Scientific Reviewer QA loop.
- **2d.** System prompts for all 11 agents (port the two prompts published in the paper's
  Supplementary Notes verbatim as the canonical style; author the rest in that style).
- **2e.** Agent **Skills** with progressive disclosure (e.g. single-cell QC/analysis workflow).
- **Done when:** a stub query routes through CSO → one scientist agent → one MCP tool → reviewer →
  synthesis, with a full audit trace written to the session workspace.

### Phase 3 — Case study 1: large-scale clinical-trial analysis
- **3a.** `ClinicalTrialData` Pydantic schema + `@model_validator` status-conditional rules
  (port directly from the paper's clinical trialist prompt).
- **3b.** Single-agent extraction: NCT ID → 3-level evidence cascade → validated JSON.
- **3c.** Parallel extraction harness (target: tens of thousands of trials; async + rate limiting;
  checkpointing). Paper ran 37,075 trials in ~6h.
- **3d.** Feature engineering: tau index, bimodality coefficient (Tabula Sapiens), Tahoe hallmark
  scores.
- **3e.** Statistics: univariate logistic / beta regression; permutation tests; GLMM adjustment;
  genetic-evidence bivariate + no-genetic-evidence subset; BH FDR.
- **3f.** Reproduce the headline numbers (cell-type-specific targets: +40% Phase I→II, +48% to
  Phase IV, −32% AE rate) on the rebuilt dataset; regenerate Figure 2 + S2–S4 analogues.
- **Done when:** the pipeline runs on a sampled subset and the statistical results reproduce within
  tolerance; manual-validation harness (100-trial audit) included.

### Phase 4 — Case study 2: B7-H3 (CD276) in lung cancer
- Single-cell + spatial (Cell2Location deconvolution, immune-neighborhood mixed models),
  cell-cell communication (LIANA), TCGA LUAD biomarker-stratified Cox survival (lifelines).
- Reviewer-triggered spatial follow-up (demonstrates the cross-division handoff narrative).
- **Done when:** the ADC-strategy report is generated from live tools and the survival/spatial
  figures (Fig 4, S5) reproduce.

### Phase 5 — Case study 3: OSMRβ in ulcerative colitis
- Statistical-genetics validation (GWAS/L2G/fine-mapping for OSMR), single-cell UC atlas DE,
  cross-trial GEO baseline OSMR/OSM comparison (5 trials), TAURUS PROGENy JAK-STAT dynamics,
  OSMR gradient program, biomarker-guided enrollment proposal.
- **Done when:** the failure-mechanism + biomarker-enrichment report is generated and Figure 5
  panels reproduce.

### Phase 6 — Web UI + session workspace
- Chat UI, live agent/tool activity, reasoning traces, downloadable artifacts, isolated
  per-session workspace.
- **Done when:** a user can run a query, watch agents work, and download code/figures/data.

### Phase 7 — Hardening
- Cost/latency telemetry, caching, retries/backoff, eval suite, docs, containerization, example
  notebooks. Reproduce the paper's cost figures ($46 B7-H3, $54 OSMR) as a sanity benchmark.

---

## 4. Dependency order (critical path)

```
Phase 0  ──▶ Phase 1a (clinicaltrials MCP) ──▶ Phase 2 (orchestration) ──▶ Phase 3 (trials case study)
                  │                                      │
                  ├─▶ Phase 1b/1c (more MCP) ────────────┤
                  └─▶ Phase 1e (sc/spatial data) ─▶ Phase 4 & 5 (sc/spatial case studies)
Phase 2 + any case study ──▶ Phase 6 (UI) ──▶ Phase 7 (hardening)
```

MCP tools gate everything. Orchestration gates the case studies. The UI and hardening come last.

---

## 5. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.10+ | matches paper |
| Orchestration | Claude Agent SDK | hierarchical sub-agents, MCP-native, multi-turn state |
| Tool servers | FastMCP | typed tools, auto schema introspection |
| Models | Sonnet 4.5 (scientists/CSO), Haiku 4.5 (CoS, Reviewer) | configurable per agent |
| Validation | Pydantic v2 | trial schema + status validators |
| Stats (Python) | statsmodels, scipy, lifelines, pingouin | logistic, mixed models, survival |
| Mixed models / beta reg | statsmodels `BetaModel`, `BinomialBayesMixedGLM`, `MixedLM` | Python-native; replaces the paper's R (lme4 / glmmTMB / betareg) |
| Single-cell | scanpy, anndata, harmonypy, pydeseq2, decoupler, liana, cell2location | sc/spatial pipelines |
| Data | cellxgene-census, pybiomart, requests/httpx | API clients |
| UI | FastAPI + WebSocket backend, lightweight React/HTMX front | live reasoning stream |
| Tests | pytest, pytest-asyncio, respx (HTTP mocks) | |
| Packaging | hatchling / pip -e, optional uv | |

---

## 6. Repository layout

```
virtual-biotech/
├── docs/                      # plan, architecture, per-phase design notes
├── src/virtual_biotech/
│   ├── config.py              # model routing, paths, credentials
│   ├── orchestration/         # cso, chief_of_staff, reviewer, router
│   ├── agents/                # base agent, registry, division configs
│   ├── prompts/               # system prompts (one .md per agent)
│   ├── skills/                # progressive-disclosure workflow skills
│   └── common/                # logging, workspace, schemas
├── mcp_servers/               # one package per FastMCP server
│   ├── clinicaltrials/        # reference implementation
│   └── ...
├── analysis/                  # reusable scientific code per case study
│   ├── trial_outcomes/
│   ├── b7h3_luad/
│   └── osmr_uc/
├── ui/                        # web interface
├── scripts/                   # data setup, batch runners
├── tests/
├── data/                      # gitignored local datasets
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 7. Risks & open questions

- **Data access & size.** CELLxGENE Census, Tabula Sapiens v2, and Tahoe-100M are large (100M+
  cells; 4B+ measurements). We gate these behind a `scripts/setup_data.py` and start with sampled
  subsets. Tahoe pseudobulk and Tabula Sapiens need local copies.
- **Open Targets surface area.** v25.09 GraphQL is broad; the open_targets server will be the
  biggest single MCP build. We'll implement tools incrementally, driven by what the case studies
  need.
- **Statistical parity with the paper's R models.** The paper used R (lme4, glmmTMB, betareg) for
  the GLMMs and beta regression; we use statsmodels (`BetaModel`, `BinomialBayesMixedGLM`). The
  mixed-effects GLMM is fit by variational Bayes (posterior mean ± SD) rather than REML/ML, so
  significance is read from whether the 95% credible interval excludes the null rather than a
  frequentist p-value. Estimates should agree closely; we validate direction/magnitude on synthetic
  data with known effects.
- **Cost & rate limits.** Parallel trial extraction at paper scale (37k agents) is expensive and
  rate-limited. The harness must checkpoint, back off, and support sampled runs by default.
- **Reproducibility drift.** Databases update (Open Targets releases, ClinicalTrials.gov records).
  Exact paper numbers may not reproduce; we pin dataset versions where possible and report deltas.
- **Information leakage.** The paper deliberately chose readouts after the model knowledge cutoff.
  For our case studies we should note where pretraining knowledge could bias results.

---

## 8. Status log

| Date | Phase | Status |
|---|---|---|
| Session 1 | 0 — Scaffold | ✅ Repo skeleton, plan, config, session workspace/audit log |
| Session 1 | 1a — Reference MCP | ✅ ClinicalTrials.gov server (validated vs live API) |
| Session 1 | 2 — Orchestration | ✅ 11-agent registry, all 11 prompts, CSO dry-run flow w/ audit trace |
| Session 2 | 1b/1c/1d — MCP servers | ✅ Open Targets, PubMed, OpenFDA, cBioPortal servers + clients |
| Session 2 | 1b — public MCP servers | ✅ DailyMed (drug labels/boxed warnings), gnomAD (constraint) |
| Session 3 | Science library | ✅ tau index, bimodality coefficient, Tahoe hallmark scores (exact-tested) |
| Session 3 | 1e — data setup | ✅ scripts/setup_data.py manifest-driven downloader + data/README |
| Session 3 | 1e — data-gated MCP | ✅ DepMap, Tahoe, Tabula Sapiens, CELLxGENE servers (graceful degradation) |
| Session 3 | Testing | ✅ 101 unit tests; all 11 MCP servers register tools + pass harness |
| | | **Phase 1 (MCP tool layer) complete.** |
| Session 4 | 3a — Trial schema | ✅ ClinicalTrialData + status-conditional validators, 16 stop categories |
| Session 4 | 3b — Evidence cascade | ✅ 3-level cascade control logic (escalation + prefill + verification) |
| Session 4 | 3c — Parallel harness | ✅ async, bounded concurrency, checkpoint/resume, error isolation |
| Session 4 | 3d/3e — Features + stats | ✅ feature join (min-across-targets), logistic OR+CI, permutation, BH FDR |
| Session 4 | 3f — End-to-end demo | ✅ analysis/trial_outcomes/run_pipeline.py reproduces headline DIRECTION (OR>1) |
| Session 4 | Testing | ✅ 142 unit tests; pipeline recovers OR≈2.7, p≈6e-19 on synthetic cohort |
| | | **Phase 3 core complete.** |
| Session 5 | 3e — Python stats (no R) | ✅ beta regression, multivariable + mixed-effects logistic via statsmodels; all 3 paper findings reproduce in pure Python |
| Session 6 | 3b — Live extractor | ✅ Open Targets cohort loader + live clinical-trialist agent extractor (Agent SDK) + cascade extractor over real CT.gov/PubMed clients |
| Session 6 | 3c — Cohort driver | ✅ analysis/trial_outcomes/extract_cohort.py: cohort→extractor→harness→feature join→stats; --demo/--agent/--limit |
| Session 6 | Testing | ✅ 166 unit tests incl. cohort parsing + end-to-end cohort integration |
| | | **Phase 3 complete.** To run at full scale: download the OT known-drugs + Tabula Sapiens datasets, set ANTHROPIC_API_KEY, run extract_cohort --mode agent. |
| Session 7 | 2a — Agent runtime | ✅ FastMCP→Agent SDK bridge (`create_sdk_mcp_server`), real `BaseAgent.run`, `vb` CLI (`list`/`agent`/`ask`), interactive `explore.py`. 177 tests. |
| | | **Agents callable end-to-end** (needs Claude Code CLI on PATH). Next: case studies. |

### MCP server status

| Server | Status | Tools |
|---|---|---|
| clinicaltrials | ✅ implemented | get_clinical_trial_details, search_clinical_trials, get_trial_adverse_events |
| open_targets | ✅ implemented | search_entities, get_target_details, get_target_genetic_evidence, get_target_known_drugs, get_disease_details, **get_gwas_credible_set_evidence (L2G), get_credible_set (fine-mapping + QTL coloc), get_variant** |
| pubmed | ✅ implemented | search_pubmed, fetch_abstract, verify_nct_in_article |
| openfda | ✅ implemented | get_top_adverse_reactions, get_report_counts |
| cbioportal | ✅ implemented | find_cancer_studies, get_study_details, get_molecular_profiles |
| dailymed | ✅ implemented | get_boxed_warning, get_label_safety_sections, find_dailymed_spls |
| gnomad | ✅ implemented | get_gene_constraint (pLI, LOEUF, LoF interpretation) |
| cellxgene | ✅ implemented (API) | get_celltype_expression |
| tabula_sapiens | ✅ implemented (data-gated) | get_celltype_specificity (tau), get_expression_heterogeneity (bimodality) |
| tahoe | ✅ implemented (data-gated) | list_hallmarks, get_drug_hallmark_scores |
| depmap | ✅ implemented (data-gated) | get_gene_essentiality |

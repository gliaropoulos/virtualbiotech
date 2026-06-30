# Virtual Biotech

A faithful, reusable re-implementation of **"The Virtual Biotech: A Multi-Agent AI Framework for
Therapeutic Discovery and Development"** (Zhang, Eckmann, Miao, Mahon & Zou, bioRxiv 2026 —
[doi:10.64898/2026.02.23.707551](https://doi.org/10.64898/2026.02.23.707551)).

The Virtual Biotech emulates a cross-functional therapeutics R&D organization as a hierarchy of
AI agents. A **Chief Scientific Officer (CSO)** orchestrator clarifies a scientific query,
decomposes it, routes sub-tasks to **eight specialized scientist agents** across **four divisions**,
and synthesizes their evidence into a recommendation. A **Chief of Staff** prepares field briefings
and a **Scientific Reviewer** does quality assurance. Agents reach data through **~10 FastMCP
servers** wrapping public biomedical databases (Open Targets, ClinicalTrials.gov, PubMed, CELLxGENE,
Tabula Sapiens, Tahoe-100M, cBioPortal, OpenFDA, and more).

> **Status:** early scaffold. See [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) for the
> phased roadmap and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the system design.

## Stack

Python 3.10+ · [Claude Agent SDK](https://docs.claude.com) (orchestration) · FastMCP (tools) ·
Claude Sonnet 4.5 (scientists/CSO) + Haiku 4.5 (Chief of Staff, Reviewer) · Pydantic · scanpy /
statsmodels / lifelines (analysis).

## Quick start (build & test, no API key needed)

```bash
cd virtualbiotech
make venv && source .venv/bin/activate    # or: python -m venv .venv && source .venv/bin/activate
make install                              # core + stats + dev deps + editable install
make test                                 # 166 tests pass without credentials
```

Without `make`, the equivalent is:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && pip install -e .
pytest
```

See [`docs/SETUP.md`](docs/SETUP.md) for the dependency layers (core / stats / dev / single-cell)
and dataset setup. To actually run agents, copy `.env.example` to `.env` and add your
`ANTHROPIC_API_KEY`.

## Talk to the agents

Once `ANTHROPIC_API_KEY` is in `.env` and the Claude Code CLI is installed
(`npm install -g @anthropic-ai/claude-code`), each agent's domain MCP tools are bridged in-process
via the Agent SDK:

```bash
vb list                                              # the 11 agents + their tools
vb agent statistical_genetics "Assess OSMR genetic evidence in ulcerative colitis"
vb ask "Evaluate OSMR as a therapeutic target in ulcerative colitis"   # full CSO orchestration
vb ask "..." --dry-run                               # routing trace only, no model calls
```

(`vb` is installed by `pip install -e .`; equivalently `python -m virtual_biotech.cli ...`.)

To explore the data tools directly without any agent/key:

```bash
python scripts/explore.py call open_targets get_target_genetic_evidence ensembl_id=ENSG00000145623
python scripts/explore.py                             # interactive REPL
```

## Run the reference MCP server

```bash
python -m mcp_servers.clinicaltrials.server      # starts the ClinicalTrials.gov FastMCP server
python -m mcp_servers.clinicaltrials.smoke NCT06137183   # one-off live tool call
```

## Layout

```
src/virtual_biotech/   orchestration, agents, prompts, skills, common utilities
mcp_servers/           one FastMCP server per data source (clinicaltrials = reference impl)
analysis/              reusable scientific code for each case study
ui/                    web interface (chat + live agent activity)
scripts/               data setup and batch runners
tests/                 pytest suite
docs/                  development plan + architecture
```

## Reproduced case studies (planned)

1. **Large-scale trial analysis** — parallel extraction of clinical-trial outcomes + single-cell
   feature/outcome statistics.
2. **B7-H3 (CD276) in lung cancer** — single-cell, spatial, and survival evidence for an ADC
   strategy.
3. **OSMRβ in ulcerative colitis** — retrospective failure analysis + biomarker-guided enrollment.

## License

Code: MIT (see `LICENSE`). The underlying paper is CC-BY-ND 4.0; this is an independent
re-implementation, not affiliated with the original authors.

## Disclaimer

Research/educational software. Generates hypotheses that require experimental validation. Not for
clinical use.

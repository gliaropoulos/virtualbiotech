# Setup guide

How to create a virtual environment and install the Virtual Biotech platform.

## Prerequisites

- Python 3.10 or newer (`python3 --version`)
- macOS / Linux (Windows works via WSL)
- An Anthropic API key — only needed to actually *run agents*; building, importing, and the full
  test suite work without one.

## Quick start (recommended)

From the repo root (`/Users/gliar/intelligencia_code/virtualbiotech`):

```bash
make venv          # creates .venv and upgrades pip
source .venv/bin/activate
make install       # core + stats + dev deps, plus an editable install of the package
make test          # 166 tests should pass
```

`make install` runs `pip install -r requirements-dev.txt && pip install -e .`. The editable
install (`-e .`) puts `virtual_biotech` on your path so you can `import virtual_biotech` and run the
MCP servers as modules without setting `PYTHONPATH`.

## Manual setup (no make)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

pip install -r requirements-dev.txt   # core + stats + test tooling
pip install -e .                      # editable install of the package
```

To deactivate later: `deactivate`.

## Dependency layers

The requirements are split so you only install what you need:

| File | What it adds | When you need it |
|---|---|---|
| `requirements.txt` | core runtime (agent SDK, FastMCP, pydantic, httpx) | always |
| `requirements-stats.txt` | numpy/scipy/pandas/statsmodels/lifelines | the clinical-trial pipeline + stats |
| `requirements-dev.txt` | the above + pytest/ruff | running tests / developing |
| `requirements-singlecell.txt` | scanpy/anndata/pydeseq2/decoupler/cellxgene-census | single-cell case studies (2 & 3) |

`requirements-dev.txt` includes `requirements-stats.txt`, which includes `requirements.txt`, so a
single `pip install -r requirements-dev.txt` gives a complete dev/test environment.

The single-cell stack is heavy and platform-specific; install it only when running those analyses:

```bash
pip install -r requirements-singlecell.txt
# liana (cell-cell communication) and cell2location (spatial; needs PyTorch) are installed
# separately — see requirements-singlecell.txt and their own docs.
```

Equivalent extras are also defined in `pyproject.toml`, so you can instead do:

```bash
pip install -e ".[dev,stats]"          # same as requirements-dev.txt + package
pip install -e ".[dev,stats,singlecell]"
```

## Configure credentials

```bash
cp .env.example .env
# edit .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is gitignored. Without a key, everything still imports and tests pass — only live agent runs
require it.

## Verify the install

```bash
pytest                                          # full suite
python analysis/trial_outcomes/run_pipeline.py  # stats demo (no key/data)
python analysis/trial_outcomes/extract_cohort.py --demo
python -m mcp_servers.clinicaltrials.smoke NCT06137183   # live API check (needs network)
```

## Optional: pin exact versions (lockfile)

The requirements files use lower bounds (`>=`) for flexibility. To freeze the exact versions you
resolved into a reproducible lockfile:

```bash
pip freeze > requirements.lock.txt
```

Then others can reproduce your environment with `pip install -r requirements.lock.txt`.

## Datasets (only for the single-cell case studies)

The public-API MCP servers need nothing local. The data-gated servers (Tabula Sapiens, Tahoe,
DepMap) and the full 55,984-trial cohort need downloads:

```bash
python scripts/setup_data.py --list     # see what's needed + status
python scripts/setup_data.py --check
```

Most of these live behind portals, so the script prints manual download instructions; see
`data/README.md`.

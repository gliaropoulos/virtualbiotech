# Virtual Biotech — common developer tasks.
# Usage: `make venv` then `make install` (or `make install-all`), then `make test`.

PYTHON ?= python3
VENV   ?= .venv
BIN     = $(VENV)/bin

.PHONY: help venv install install-all install-singlecell test lint run-demo run-cohort clean

help:
	@echo "Targets:"
	@echo "  venv               create a virtual environment in $(VENV)"
	@echo "  install            install core + stats + dev (editable) — recommended"
	@echo "  install-all        also install the single-cell/spatial stack"
	@echo "  test               run the full pytest suite"
	@echo "  lint               run ruff"
	@echo "  run-demo           run the trial-outcome pipeline demo (no API key/data needed)"
	@echo "  run-cohort         run the cohort extraction demo"
	@echo "  clean              remove venv + caches"

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	@echo "Created $(VENV). Activate with: source $(VENV)/bin/activate"

install:
	$(BIN)/pip install -r requirements-dev.txt
	$(BIN)/pip install -e .
	@echo "Installed. Copy .env.example to .env and add ANTHROPIC_API_KEY to run agents."

install-all: install
	$(BIN)/pip install -r requirements-singlecell.txt

test:
	$(BIN)/python -m pytest

lint:
	$(BIN)/ruff check src mcp_servers tests

run-demo:
	$(BIN)/python analysis/trial_outcomes/run_pipeline.py

run-cohort:
	$(BIN)/python analysis/trial_outcomes/extract_cohort.py --demo

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache **/__pycache__ *.egg-info src/*.egg-info

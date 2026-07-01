"""Central configuration: model routing, paths, and credential loading.

Importing this module never requires secrets. Missing credentials only surface
when an agent or tool actually tries to use them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional convenience; not required
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

# A blank `ANTHROPIC_API_KEY=` line in .env sets the var to "" in the environment, which the Claude
# CLI still counts as an auth source and uses *instead of* your claude.ai subscription login. Drop
# empty/whitespace values so subscription (OAuth) auth can take over cleanly.
if not (os.getenv("ANTHROPIC_API_KEY") or "").strip():
    os.environ.pop("ANTHROPIC_API_KEY", None)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("VB_DATA_DIR", REPO_ROOT / "data"))
SESSIONS_DIR = REPO_ROOT / "sessions"

# Model identifiers (overridable via env). Defaults match the paper.
MODEL_ORCHESTRATOR = os.getenv("VB_MODEL_ORCHESTRATOR", "claude-sonnet-4-5")
MODEL_SCIENTIST = os.getenv("VB_MODEL_SCIENTIST", "claude-sonnet-4-5")
MODEL_SUPPORT = os.getenv("VB_MODEL_SUPPORT", "claude-haiku-4-5")  # Chief of Staff, Reviewer


@dataclass(frozen=True)
class Endpoints:
    open_targets: str = os.getenv(
        "OPEN_TARGETS_GRAPHQL", "https://api.platform.opentargets.org/api/v4/graphql"
    )
    clinicaltrials: str = os.getenv("CLINICALTRIALS_API", "https://clinicaltrials.gov/api/v2")
    cbioportal: str = os.getenv("CBIOPORTAL_API", "https://www.cbioportal.org/api")
    ncbi_eutils: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    openfda: str = "https://api.fda.gov"


ENDPOINTS = Endpoints()


def anthropic_api_key() -> str | None:
    """Return the Anthropic API key if configured, else None (build/test-safe)."""
    return os.getenv("ANTHROPIC_API_KEY") or None


def require_anthropic_api_key() -> str:
    key = anthropic_api_key()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key


def claude_cli_path() -> str | None:
    """Prefer an explicit override, then the system `claude` binary over the SDK bundle."""
    override = os.getenv("VB_CLAUDE_CLI_PATH")
    if override:
        path = Path(override)
        return str(path) if path.exists() else override
    from shutil import which
    return which("claude")

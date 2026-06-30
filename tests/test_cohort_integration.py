"""Integration test: cohort -> extractor -> harness -> feature join -> association.

Exercises the case-study-1 driver's helpers end to end on the synthetic cohort (no network/key).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "extract_cohort", ROOT / "analysis" / "trial_outcomes" / "extract_cohort.py")
extract_cohort = importlib.util.module_from_spec(_spec)
sys.modules["extract_cohort"] = extract_cohort
_spec.loader.exec_module(extract_cohort)

from virtual_biotech.trials import cohort as cohort_mod  # noqa: E402
from virtual_biotech.trials import outcomes, pipeline  # noqa: E402
from virtual_biotech.trials.harness import ExtractionHarness  # noqa: E402


@pytest.mark.asyncio
async def test_cohort_demo_pipeline_recovers_association(tmp_path):
    stubs, gold, tau_lookup, gen_lookup = extract_cohort.synthetic_cohort(n=400, seed=0)
    extractor = extract_cohort.make_extractor("demo", gold, cohort_mod.target_lookup(stubs))

    harness = ExtractionHarness(tmp_path, concurrency=16)
    stats_run = await harness.run([s.nct_id for s in stubs], extractor)
    assert stats_run.completed == 400 and stats_run.failed == 0
    assert len(list(tmp_path.glob("NCT*.json"))) == 400

    records = harness.load_results()
    assoc = pipeline.associate(
        records, feature_name="tau", lookup=tau_lookup,
        outcome_name="endpoint_success", outcome_fn=outcomes.endpoint_success)
    assert assoc.result.odds_ratio > 1.0          # specificity -> success, recovered via the cohort path
    assert assoc.result.p_value < 0.05


def test_synthetic_cohort_shapes():
    stubs, gold, tau_lookup, gen_lookup = extract_cohort.synthetic_cohort(n=50)
    assert len(stubs) == 50 and len(gold) == 50
    assert all(s.phase in (2, 3) for s in stubs)
    # every trial's target has a tau feature
    assert all(g in tau_lookup for s in stubs for g in s.targets)

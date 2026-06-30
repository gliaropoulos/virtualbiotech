"""End-to-end driver for case study 1: extract the Open Targets cohort, then test associations.

Pipeline:
    Open Targets cohort (NCT IDs + targets, Phase II/III)
      -> live clinical-trialist extractor (per-trial agent OR cascade)  [ExtractionHarness, checkpointed]
      -> single-cell feature join (Tabula Sapiens tau, min across targets)
      -> univariate logistic / beta regression / genetic-adjusted associations

Modes:
    --demo            self-contained synthetic cohort+features+outcomes; no network/key/data needed.
    --mode cascade    deterministic cascade extractor over the real ClinicalTrials.gov/PubMed clients
                      (requires network; the per-field reasoning step must be supplied to go beyond
                      registry data — see make_cascade_extractor).
    --mode agent      per-trial clinical-trialist agent (requires Claude Agent SDK + ANTHROPIC_API_KEY).
    --limit N         sample the first N trials (use for a small real run before scaling to 55,984).

Usage:
    python analysis/trial_outcomes/extract_cohort.py --demo
    python analysis/trial_outcomes/extract_cohort.py --mode agent --limit 50 --out runs/cohort
"""
from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path

import numpy as np

from virtual_biotech.trials import cohort as cohort_mod
from virtual_biotech.trials import outcomes, pipeline
from virtual_biotech.trials.cohort import TrialStub
from virtual_biotech.trials.harness import ExtractionHarness
from virtual_biotech.trials.schema import (
    AdverseEventProfile, ClinicalTrialData, EndpointResult, TrialStatus,
)


# --------------------------------------------------------------------------- demo data
def synthetic_cohort(n: int = 500, seed: int = 0):
    """A synthetic stand-in for the Open Targets cohort + hidden tau features + gold outcomes."""
    rng = np.random.default_rng(seed)
    stubs, gold, tau_lookup, gen_lookup = [], {}, {}, {}
    for i in range(n):
        gene, nct = f"G{i}", f"NCT{i:08d}"
        tau = float(rng.uniform(0, 1))
        tau_lookup[gene] = tau
        gen_lookup[gene] = float(rng.integers(0, 2))
        stubs.append(TrialStub(nct, (gene,), phase=2 if i % 2 else 3))
        success = rng.random() < 1 / (1 + np.exp(-(-1.0 + 3.0 * tau)))
        ae = float(np.clip(1 / (1 + np.exp(-(-1.0 - 2.0 * tau))) * rng.uniform(0.8, 1.2), 0, 1))
        gold[nct] = ClinicalTrialData(
            nctId=nct, overallStatus=TrialStatus.COMPLETED, targets=[gene],
            primaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            secondaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            adverseEventProfile=AdverseEventProfile(seriousAeRate=ae))
    return stubs, gold, tau_lookup, gen_lookup


# --------------------------------------------------------------------------- feature join
def tabula_tau_lookup(stubs: list[TrialStub]) -> dict[str, float]:
    """Compute Tabula Sapiens tau per unique target via the data-gated server (empty if absent)."""
    from mcp_servers.tabula_sapiens import data as ts
    if not ts.is_available():
        return {}
    genes = {g for s in stubs for g in s.targets}
    out = {}
    for g in genes:
        feats = ts.compute_gene_features(g)
        if feats and feats.get("found") and feats.get("tau") is not None:
            out[g] = feats["tau"]
    return out


# --------------------------------------------------------------------------- run
async def run(stubs, extractor, tau_lookup, gen_lookup, out_dir, *, permutations: int = 200):
    harness = ExtractionHarness(out_dir, concurrency=32)
    stats_run = await harness.run([s.nct_id for s in stubs], extractor)
    print("Extraction:", stats_run.summary())
    if stats_run.errors:
        print(f"  ({len(stats_run.errors)} failures, e.g. "
              f"{next(iter(stats_run.errors.items()))})")
    records = harness.load_results()
    if not records:
        print("No validated records produced; aborting analysis.")
        return

    assoc = pipeline.associate(
        records, feature_name="tau", lookup=tau_lookup, outcome_name="endpoint_success",
        outcome_fn=outcomes.endpoint_success, permutations=permutations)
    r = assoc.result
    print(f"\n[logistic] tau ~ endpoint_success (n={r.n}): OR/SD={r.odds_ratio:.2f} "
          f"(95% CI {r.ci_low:.2f}-{r.ci_high:.2f}), p={r.p_value:.2e}, perm p={assoc.perm_p}")

    try:
        br = pipeline.associate_rate(
            records, feature_name="tau", lookup=tau_lookup,
            rate_name="serious_ae_rate", rate_fn=outcomes.serious_ae_rate)
        print(f"[beta]     tau ~ serious_ae_rate (n={br.n}): logit-mean shift/SD={br.coef:.3f} "
              f"(95% CI {br.ci_low:.3f}-{br.ci_high:.3f})")
    except ValueError as e:
        print(f"[beta]     skipped ({e})")

    if gen_lookup:
        adj = pipeline.associate_adjusted(
            records, feature_name="tau", lookup=tau_lookup, outcome_name="endpoint_success",
            outcome_fn=outcomes.endpoint_success, covariate_lookups={"genetic_evidence": gen_lookup})
        print(f"[adjusted] tau ~ success | genetic_evidence (n={adj.n}): "
              f"OR/SD={adj.effect_size:.2f} (95% CI {adj.ci_low:.2f}-{adj.ci_high:.2f})")


def make_extractor(mode: str, gold, cohort_targets):
    if mode == "demo":
        async def extractor(nct):
            return gold[nct]
        return extractor
    if mode == "agent":
        from virtual_biotech.trials.agent_extractor import make_agent_extractor
        return make_agent_extractor(cohort_targets)
    if mode == "cascade":
        raise SystemExit("cascade mode needs a reasoning callable (LLM) — wire make_cascade_extractor "
                         "with your reason fn; registry-only data cannot fill endpoint results.")
    raise SystemExit(f"unknown mode '{mode}'")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--demo", action="store_true", help="run the self-contained synthetic demo")
    p.add_argument("--mode", choices=["agent", "cascade"], default="agent")
    p.add_argument("--limit", type=int, default=None, help="use only the first N trials")
    p.add_argument("--out", default=None, help="output dir for per-trial JSON (default: temp)")
    p.add_argument("--permutations", type=int, default=200)
    args = p.parse_args(argv)

    if args.demo:
        stubs, gold, tau_lookup, gen_lookup = synthetic_cohort()
        if args.limit:
            stubs = stubs[:args.limit]
        extractor = make_extractor("demo", gold, cohort_mod.target_lookup(stubs))
    else:
        stubs = cohort_mod.load_cohort()
        if stubs is None:
            raise SystemExit("Open Targets cohort not installed. Run "
                             "`python scripts/setup_data.py --dataset open_targets_known_drugs`, "
                             "or use --demo.")
        if args.limit:
            stubs = stubs[:args.limit]
        print(f"Loaded {len(stubs)} Phase II/III trials from Open Targets.")
        tau_lookup = tabula_tau_lookup(stubs)
        gen_lookup = {}     # populate from the Open Targets MCP genetic-evidence tool for a real run
        extractor = make_extractor(args.mode, {}, cohort_mod.target_lookup(stubs))

    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="vb_cohort_"))
    asyncio.run(run(stubs, extractor, tau_lookup, gen_lookup, out_dir,
                    permutations=args.permutations))
    print(f"\nPer-trial JSON written under: {out_dir}")


if __name__ == "__main__":
    main()

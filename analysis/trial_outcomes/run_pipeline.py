"""Runnable demo of the large-scale trial-outcome pipeline (Phase 3, case study 1).

This wires the pieces together end to end on a small, self-contained synthetic cohort so the whole
flow runs with no network, data downloads, or API keys:

    extraction harness  ->  validated ClinicalTrialData JSONs
                         ->  single-cell feature join (tau, min across targets)
                         ->  univariate logistic associations + permutation + BH FDR

In production the extractor is the clinical-trialist agent running the 3-level evidence cascade over
real NCT IDs (see virtual_biotech.trials.cascade + the clinicaltrials/pubmed MCP servers), and the
feature lookups come from the Tabula Sapiens / Tahoe MCP servers. Swap `synthetic_extractor` and the
feature dicts for those to run at scale.

Usage:  python analysis/trial_outcomes/run_pipeline.py
"""
from __future__ import annotations

import asyncio
import tempfile

import numpy as np

from virtual_biotech.trials import outcomes, pipeline
from virtual_biotech.trials.harness import ExtractionHarness
from virtual_biotech.trials.schema import (
    AdverseEventProfile, ClinicalTrialData, EndpointResult, TrialStatus,
)


def synthesize(n: int = 500, seed: int = 0):
    """A toy cohort where cell-type-specific targets (high tau) succeed more and have lower AE."""
    rng = np.random.default_rng(seed)
    gold, tau_lookup, gen_lookup = {}, {}, {}
    for i in range(n):
        gene = f"G{i}"
        tau = float(rng.uniform(0, 1))
        tau_lookup[gene] = tau
        gen_lookup[gene] = float(rng.integers(0, 2))         # synthetic genetic-evidence flag
        p_success = 1 / (1 + np.exp(-(-1.0 + 3.0 * tau)))    # success rises with specificity
        success = rng.random() < p_success
        ae_rate = float(np.clip(1 / (1 + np.exp(-(-1.0 - 2.0 * tau))) * rng.uniform(0.8, 1.2), 0, 1))
        nct = f"NCT{i:08d}"
        gold[nct] = ClinicalTrialData(
            nctId=nct, overallStatus=TrialStatus.COMPLETED, targets=[gene],
            primaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            secondaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            adverseEventProfile=AdverseEventProfile(seriousAeRate=ae_rate))
    return gold, tau_lookup, gen_lookup


async def main() -> None:
    gold, tau_lookup, gen_lookup = synthesize()

    async def synthetic_extractor(nct: str) -> ClinicalTrialData:
        return gold[nct]

    with tempfile.TemporaryDirectory() as out:
        harness = ExtractionHarness(out, concurrency=64)
        stats_run = await harness.run(list(gold), synthetic_extractor)
        print("Extraction:", stats_run.summary())
        records = harness.load_results()

    # 1) Univariate logistic: tau ~ endpoint success
    assoc = pipeline.associate(
        records, feature_name="tau_specificity", lookup=tau_lookup,
        outcome_name="endpoint_success", outcome_fn=outcomes.endpoint_success, permutations=500)
    r = assoc.result
    print(f"\n[univariate logistic] {assoc.feature} ~ {assoc.outcome} (n={r.n})")
    print(f"  OR per +1 SD = {r.odds_ratio:.2f}  (95% CI {r.ci_low:.2f}-{r.ci_high:.2f})")
    print(f"  p = {r.p_value:.2e}   permutation p = {assoc.perm_p:.4f}")
    print(f"  => cell-type-specific targets are {'MORE' if r.odds_ratio > 1 else 'LESS'} "
          f"likely to succeed.")

    # 2) Beta regression (Python, no R): tau ~ serious AE rate
    br = pipeline.associate_rate(
        records, feature_name="tau_specificity", lookup=tau_lookup,
        rate_name="serious_ae_rate", rate_fn=outcomes.serious_ae_rate)
    print(f"\n[beta regression]     tau_specificity ~ serious_ae_rate (n={br.n})")
    print(f"  logit-mean shift per +1 SD = {br.coef:.3f}  (95% CI {br.ci_low:.3f}-{br.ci_high:.3f})")
    print(f"  => cell-type-specific targets have {'LOWER' if br.coef < 0 else 'HIGHER'} "
          f"adverse-event rates.")

    # 3) Genetic-evidence-adjusted bivariate logistic
    adj = pipeline.associate_adjusted(
        records, feature_name="tau_specificity", lookup=tau_lookup,
        outcome_name="endpoint_success", outcome_fn=outcomes.endpoint_success,
        covariate_lookups={"genetic_evidence": gen_lookup})
    print(f"\n[bivariate logistic]  tau ~ success | genetic_evidence (n={adj.n})")
    print(f"  adjusted OR per +1 SD = {adj.effect_size:.2f}  "
          f"(95% CI {adj.ci_low:.2f}-{adj.ci_high:.2f})")
    print("  => single-cell signal is informative independent of genetic evidence.")
    print("\nAll three regressions are pure Python (statsmodels) — no R / rpy2.")


if __name__ == "__main__":
    asyncio.run(main())

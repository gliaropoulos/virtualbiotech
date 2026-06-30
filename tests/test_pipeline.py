"""Tests for outcome extraction and the end-to-end feature/outcome association pipeline."""
import numpy as np
import pytest

from virtual_biotech.trials import outcomes, pipeline
from virtual_biotech.trials.schema import (
    AdverseEventProfile, ClinicalTrialData, EndpointResult, StopReasonCategory, TrialStatus,
)


# ---- outcome extractors ------------------------------------------------------

def test_endpoint_success_mapping():
    pos = ClinicalTrialData(nctId="NCT00000001", overallStatus=TrialStatus.COMPLETED,
                            primaryEndpointResult=EndpointResult.POSITIVE,
                            secondaryEndpointResult=EndpointResult.POSITIVE)
    neg = ClinicalTrialData(nctId="NCT00000002", overallStatus=TrialStatus.COMPLETED,
                            primaryEndpointResult=EndpointResult.NEGATIVE,
                            secondaryEndpointResult=EndpointResult.NEGATIVE)
    unk = ClinicalTrialData(nctId="NCT00000003", overallStatus=TrialStatus.COMPLETED,
                            primaryEndpointResult=EndpointResult.UNKNOWN,
                            secondaryEndpointResult=EndpointResult.UNKNOWN)
    assert outcomes.endpoint_success(pos) == 1
    assert outcomes.endpoint_success(neg) == 0
    assert outcomes.endpoint_success(unk) is None


def test_terminated_for_efficacy():
    t = ClinicalTrialData(nctId="NCT00000004", overallStatus=TrialStatus.TERMINATED,
                          studyStopReason="lack of efficacy",
                          studyStopReasonCategories=[StopReasonCategory.NEGATIVE_LACK_OF_EFFICACY])
    biz = ClinicalTrialData(nctId="NCT00000005", overallStatus=TrialStatus.TERMINATED,
                            studyStopReason="sponsor decision",
                            studyStopReasonCategories=[StopReasonCategory.BUSINESS_OR_ADMINISTRATIVE])
    completed = ClinicalTrialData(nctId="NCT00000006", overallStatus=TrialStatus.COMPLETED,
                                  primaryEndpointResult=EndpointResult.POSITIVE,
                                  secondaryEndpointResult=EndpointResult.POSITIVE)
    assert outcomes.terminated_for_efficacy(t) == 1
    assert outcomes.terminated_for_efficacy(biz) == 0
    assert outcomes.terminated_for_efficacy(completed) is None


def test_serious_ae_rate_from_counts():
    t = ClinicalTrialData(nctId="NCT00000007", overallStatus=TrialStatus.COMPLETED,
                          primaryEndpointResult=EndpointResult.POSITIVE,
                          secondaryEndpointResult=EndpointResult.POSITIVE,
                          adverseEventProfile=AdverseEventProfile(seriousEventCount=5,
                                                                  totalParticipants=100))
    assert outcomes.serious_ae_rate(t) == pytest.approx(0.05)


# ---- feature aggregation -----------------------------------------------------

def test_trial_feature_min_across_targets():
    t = ClinicalTrialData(nctId="NCT00000008", overallStatus=TrialStatus.RECRUITING,
                          targets=["A", "B", "C"])
    lookup = {"A": 0.9, "B": 0.3, "C": 0.7}
    assert pipeline.trial_feature(t, lookup) == pytest.approx(0.3)   # min rule


def test_build_xy_drops_missing():
    recs = [
        ClinicalTrialData(nctId="NCT00000009", overallStatus=TrialStatus.COMPLETED,
                          primaryEndpointResult=EndpointResult.POSITIVE,
                          secondaryEndpointResult=EndpointResult.POSITIVE, targets=["A"]),
        ClinicalTrialData(nctId="NCT00000010", overallStatus=TrialStatus.COMPLETED,
                          primaryEndpointResult=EndpointResult.UNKNOWN,        # outcome None -> dropped
                          secondaryEndpointResult=EndpointResult.UNKNOWN, targets=["A"]),
        ClinicalTrialData(nctId="NCT00000011", overallStatus=TrialStatus.COMPLETED,
                          primaryEndpointResult=EndpointResult.NEGATIVE,
                          secondaryEndpointResult=EndpointResult.NEGATIVE, targets=["Z"]),  # no feature
    ]
    x, y = pipeline.build_xy(recs, {"A": 0.8}, outcomes.endpoint_success)
    assert len(x) == 1 and len(y) == 1


# ---- end-to-end reproduction of the headline DIRECTION -----------------------

def _synthetic_trials(n=400, seed=0):
    """Generate trials where cell-type-specific targets (high tau) succeed more often."""
    rng = np.random.default_rng(seed)
    records, lookup = [], {}
    for i in range(n):
        gene = f"G{i}"
        tau = float(rng.uniform(0, 1))
        lookup[gene] = tau
        # success probability rises with tau (true positive association)
        p = 1 / (1 + np.exp(-(-1.0 + 3.0 * tau)))  # logit = -1 + 3*tau
        success = rng.random() < p
        records.append(ClinicalTrialData(
            nctId=f"NCT{i:08d}", overallStatus=TrialStatus.COMPLETED,
            primaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            secondaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            targets=[gene]))
    return records, lookup


def test_pipeline_recovers_positive_tau_association():
    records, lookup = _synthetic_trials()
    assoc = pipeline.associate(
        records, feature_name="tau", lookup=lookup,
        outcome_name="endpoint_success", outcome_fn=outcomes.endpoint_success,
        permutations=200)
    # cell-type-specific targets should be MORE likely to succeed: OR > 1, significant
    assert assoc.result.odds_ratio > 1.0
    assert assoc.result.p_value < 0.05
    assert assoc.perm_p < 0.05


def test_run_grid_attaches_qvalues():
    records, lookup = _synthetic_trials(seed=2)
    assocs = pipeline.run_grid(
        records, {"tau": lookup}, {"endpoint_success": outcomes.endpoint_success})
    assert len(assocs) == 1
    assert assocs[0].q_value is not None


# ---- Python-native AE-rate beta regression + genetic-adjusted associations ----

def _trials_with_ae_and_genetics(n=300, seed=4):
    rng = np.random.default_rng(seed)
    records, tau_lookup, gen_lookup = [], {}, {}
    for i in range(n):
        gene = f"G{i}"
        tau = float(rng.uniform(0, 1))
        tau_lookup[gene] = tau
        gen_lookup[gene] = float(rng.integers(0, 2))
        # higher specificity (tau) -> lower serious AE rate (paper direction)
        ae_logit = -1.0 - 2.0 * tau
        ae_rate = float(np.clip(1 / (1 + np.exp(-ae_logit)) * rng.uniform(0.8, 1.2), 0, 1))
        success = rng.random() < 1 / (1 + np.exp(-(-1.0 + 3.0 * tau)))
        records.append(ClinicalTrialData(
            nctId=f"NCT{i:08d}", overallStatus=TrialStatus.COMPLETED, targets=[gene],
            primaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            secondaryEndpointResult=EndpointResult.POSITIVE if success else EndpointResult.NEGATIVE,
            adverseEventProfile=AdverseEventProfile(seriousAeRate=ae_rate)))
    return records, tau_lookup, gen_lookup


def test_associate_rate_beta_regression():
    records, tau_lookup, _ = _trials_with_ae_and_genetics()
    res = pipeline.associate_rate(
        records, feature_name="tau", lookup=tau_lookup,
        rate_name="serious_ae_rate", rate_fn=outcomes.serious_ae_rate)
    # cell-type-specific targets -> LOWER AE rate -> negative logit-mean shift
    assert res.effect == "logit-mean shift"
    assert res.coef < 0
    assert res.ci_high < 0


def test_associate_adjusted_for_genetic_evidence():
    records, tau_lookup, gen_lookup = _trials_with_ae_and_genetics(seed=6)
    res = pipeline.associate_adjusted(
        records, feature_name="tau", lookup=tau_lookup,
        outcome_name="endpoint_success", outcome_fn=outcomes.endpoint_success,
        covariate_lookups={"genetic_evidence": gen_lookup})
    # tau remains positively associated with success after adjusting for genetic evidence
    assert res.effect == "odds ratio"
    assert res.effect_size > 1.0

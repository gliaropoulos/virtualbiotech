"""Exact-value tests for Tahoe hallmark signature scores."""
import pytest

from virtual_biotech.science import perturbation as pert


def test_apoptosis_mean_over_full_gene_set():
    hm = pert.HALLMARKS["apoptosis"]            # 11 genes, direction +1
    lfc = {"BAX": 1.0, "CASP3": 2.0}            # other genes absent -> contribute 0
    # S = (+1 / 11) * (1 + 2) = 3/11
    assert pert.hallmark_score(lfc, hm) == pytest.approx(3 / 11)


def test_direction_coefficient_flips_sign():
    hm = pert.HALLMARKS["proliferation_suppression"]   # direction -1, 11 genes
    lfc = {"MKI67": 2.0}
    assert pert.hallmark_score(lfc, hm) == pytest.approx(-2 / 11)


def test_cell_cycle_arrest_mixed_signs():
    hm = pert.HALLMARKS["cell_cycle_arrest"]    # 4 (+) genes + 3 opposite (-) genes = 7 members
    lfc = {"CDKN1A": 1.0, "CCNB1": 2.0}         # +1 from CDKN1A, -2 from CCNB1
    # total = 1 - 2 = -1 ; S = (+1 * -1) / 7
    assert pert.hallmark_score(lfc, hm) == pytest.approx(-1 / 7)


def test_filter_significant_zeros_nonsignificant():
    lfc = {"BAX": 5.0, "CASP3": 5.0}
    adj_p = {"BAX": 0.2, "CASP3": 0.01}         # BAX not significant -> zeroed
    filtered = pert.filter_significant(lfc, adj_p)
    assert filtered == {"BAX": 0.0, "CASP3": 5.0}


def test_hallmark_score_respects_significance():
    hm = pert.HALLMARKS["apoptosis"]
    lfc = {"BAX": 3.0, "CASP3": 3.0}
    adj_p = {"BAX": 0.5, "CASP3": 0.001}        # only CASP3 counts
    assert pert.hallmark_score(lfc, hm, adj_p) == pytest.approx(3 / 11)


def test_all_six_hallmarks_present():
    scores = pert.all_hallmark_scores({"BAX": 1.0})
    assert set(scores) == {
        "apoptosis", "proliferation_suppression", "dna_damage_response",
        "stress_response", "resistance", "cell_cycle_arrest",
    }
    assert scores["apoptosis"] == pytest.approx(1 / 11)


def test_missing_genes_count_toward_denominator():
    # Only one gene perturbed but the score divides by the full curated set size (11).
    hm = pert.HALLMARKS["apoptosis"]
    assert pert.hallmark_score({"BAX": 11.0}, hm) == pytest.approx(1.0)

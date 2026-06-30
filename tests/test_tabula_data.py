"""Offline tests for Tabula Sapiens feature aggregation (min-cell filter, tau, bimodality)."""
import numpy as np
import pytest
from mcp_servers.tabula_sapiens import data


def test_tau_min_cell_filter_and_aggregation():
    per_tissue = {
        "lung": {"A": (1.0, 50), "B": (0.0, 50), "C": (0.0, 10)},   # C dropped (n<20) -> means[1,0]
        "blood": {"X": (1.0, 30), "Y": (1.0, 30)},                  # uniform -> tau 0
    }
    res = data.tau_from_tissue_celltype_means(per_tissue)
    assert res["perTissue"]["lung"] == pytest.approx(1.0)
    assert res["perTissue"]["blood"] == pytest.approx(0.0)
    assert res["tau"] == pytest.approx(0.5)            # mean(1.0, 0.0)
    assert res["nTissues"] == 2
    assert res["specificity"] == "broadly expressed"   # 0.5 < 0.69


def test_tau_all_celltypes_filtered_out():
    res = data.tau_from_tissue_celltype_means({"lung": {"A": (1.0, 5)}})  # below min cells
    assert res["tau"] is None
    assert res["nTissues"] == 0


def test_bimodality_aggregation_skips_undefined():
    balanced = (np.array([1.0] * 2000 + [2.0] * 2000)).tolist()
    res = data.bimodality_from_tissue_values({"lung": balanced, "tiny": [1.0, 2.0]})  # tiny -> None
    assert res["perTissue"]["lung"] == pytest.approx(1.0, abs=3e-3)
    assert res["perTissue"]["tiny"] is None
    assert res["bimodal"] is True
    assert res["nTissues"] == 1

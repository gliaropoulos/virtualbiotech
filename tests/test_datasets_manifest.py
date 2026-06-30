"""Tests for the dataset manifest used by setup_data.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import datasets as ds


def test_expected_datasets_present():
    assert set(ds.DATASETS) == {
        "open_targets_known_drugs", "tabula_sapiens", "tahoe", "depmap", "cellxgene"}


def test_gated_excludes_api_only():
    gated = {d.key for d in ds.gated_datasets()}
    assert gated == {"open_targets_known_drugs", "tabula_sapiens", "tahoe", "depmap"}


def test_every_gated_dataset_has_dest_and_instructions():
    for d in ds.gated_datasets():
        assert d.dest and d.dest != "(none — API)"
        assert d.server
        assert d.url or d.manual          # either fetchable or has manual steps

"""Dataset manifest for the data-gated single-cell MCP servers.

Each entry declares where a dataset lives locally (relative to VB_DATA_DIR) and how to obtain it.
Some sources require a portal selection or a release-specific URL that changes over time; those have
`url=None` and rely on `manual` instructions. Keeping this as plain data (no I/O) makes it importable
and unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dataset:
    key: str
    description: str
    dest: str                       # path under VB_DATA_DIR
    server: str                     # which MCP server consumes it
    url: str | None = None          # direct download URL, if stable
    sha256: str | None = None       # optional integrity check
    approx_size: str = "unknown"
    manual: str = ""                # human instructions when url is None / login required
    sample_url: str | None = None   # smaller subset for quick local testing


DATASETS: dict[str, Dataset] = {d.key: d for d in [
    Dataset(
        key="open_targets_known_drugs",
        description="Open Targets known-drugs dataset — the clinical-trial cohort (NCT IDs, target, "
                    "phase, status) the clinical-trialist agents annotate (~55,984 trials).",
        dest="open_targets/known_drugs.parquet",
        server="(trials cohort)",
        url=None,
        approx_size="~hundreds of MB",
        manual=(
            "From the Open Targets bulk downloads (https://platform.opentargets.org/downloads, "
            "release 25.09), fetch the 'knownDrugsAggregated' dataset (Parquet) and concatenate the "
            "parts into known_drugs.parquet at the dest path. Required columns: approvedSymbol, "
            "phase, status, ctIds (list of NCT IDs), label (disease), prefName (drug)."
        ),
    ),
    Dataset(
        key="tabula_sapiens",
        description="Tabula Sapiens v2 healthy reference atlas (27 tissues) — tau / bimodality features.",
        dest="tabula_sapiens/tabula_sapiens_v2.h5ad",
        server="tabula_sapiens",
        url=None,
        approx_size="~12 GB",
        manual=(
            "Download the Tabula Sapiens v2 objects from https://tabula-sapiens.sf.czbiohub.org/ "
            "(or the CZ CELLxGENE collection). Save the whole-atlas .h5ad to the dest path. A "
            "per-tissue split is also fine — point VB_DATA_DIR/tabula_sapiens at the directory."
        ),
    ),
    Dataset(
        key="tahoe",
        description="Tahoe-100M perturbation pseudobulk LFC profiles (50 lines x 1,100 drugs).",
        dest="tahoe/tahoe100m_pseudobulk_lfc.parquet",
        server="tahoe",
        url=None,
        approx_size="~several GB (pseudobulk subset)",
        manual=(
            "Obtain Tahoe-100M from the HuggingFace dataset 'tahoebio/Tahoe-100M' (or the Arc "
            "Institute release). Export the per drug-cell-line pseudobulk log2 fold-changes at max "
            "dose with adjusted p-values to a Parquet with columns: "
            "[drug, cell_line, gene, lfc, padj]. Save to the dest path."
        ),
    ),
    Dataset(
        key="depmap",
        description="DepMap CRISPR gene-effect (Chronos) matrix — essentiality across cell lines.",
        dest="depmap/CRISPRGeneEffect.csv",
        server="depmap",
        url=None,
        approx_size="~400 MB",
        manual=(
            "From https://depmap.org/portal/data_page/ download the latest 'CRISPRGeneEffect.csv' "
            "(Chronos gene effect; rows = cell lines, columns = 'GENE (entrez)'). Save to dest. "
            "Lower (more negative) gene-effect = stronger dependency; ~ -1 = median essential."
        ),
    ),
    Dataset(
        key="cellxgene",
        description="CELLxGENE Census — accessed live via the cellxgene-census API (no local download).",
        dest="(none — API)",
        server="cellxgene",
        url=None,
        approx_size="n/a (streamed)",
        manual=(
            "No download needed. `pip install cellxgene-census`; the server queries a pinned Census "
            "release at runtime. Optionally set VB_CENSUS_VERSION to pin a release."
        ),
    ),
]}


def gated_datasets() -> list[Dataset]:
    """Datasets that actually need a local file present."""
    return [d for d in DATASETS.values() if d.dest != "(none — API)"]

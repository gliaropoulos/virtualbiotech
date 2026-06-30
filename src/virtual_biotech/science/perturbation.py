"""Tahoe-100M drug-perturbation hallmark signature scores (Zhang et al. 2026, Methods).

For each drug-cell-line combination, log2 fold-change (LFC) values are taken at maximum dose, and
non-significant changes (adjusted p >= 0.05) are zeroed. A hallmark score is the mean LFC across a
curated gene set, with a direction coefficient so that positive scores indicate drug efficacy:

    S_h = (d_h / |G_h|) * sum_{g in G_h} LFC_g

The six hallmark gene sets and direction coefficients below are exactly those listed in the paper.
Cell-cycle arrest is special: it mixes +1 genes (CDK inhibitors) and -1 genes (cyclins), so it is
represented as two signed sub-sets. All functions are pure and unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass

SIG_ADJ_P = 0.05  # changes with adjusted p >= this are set to zero before scoring


@dataclass(frozen=True)
class Hallmark:
    name: str
    direction: int                     # +1 or -1 applied to the whole set
    genes: tuple[str, ...]
    # optional genes carrying the opposite sign within the same hallmark (cell-cycle arrest)
    opposite_genes: tuple[str, ...] = ()


HALLMARKS: dict[str, Hallmark] = {
    "apoptosis": Hallmark(
        "apoptosis", +1,
        ("BAX", "CASP3", "CASP9", "BAK1", "BID", "BBC3", "PMAIP1", "APAF1", "CASP7", "CASP8", "DIABLO"),
    ),
    "proliferation_suppression": Hallmark(
        "proliferation_suppression", -1,
        ("MKI67", "PCNA", "TOP2A", "CCNB1", "CCNB2", "CDK1", "AURKA", "AURKB", "BIRC5", "FOXM1", "BUB1"),
    ),
    "dna_damage_response": Hallmark(
        "dna_damage_response", +1,
        ("GADD45A", "MDM2", "CDKN1A", "BBC3", "SESN1"),
    ),
    "stress_response": Hallmark(
        "stress_response", +1,
        ("DDIT3", "ATF4", "HSPA5", "ATF3", "XBP1", "HSPA1A", "DNAJB1", "HSPB1", "EIF2AK3", "ERN1", "PPP1R15A"),
    ),
    "resistance": Hallmark(
        "resistance", +1,
        ("BCL2", "MCL1", "XIAP", "BCL2L1", "BIRC2", "BIRC3", "CFLAR", "BCL2A1"),
    ),
    # Cell-cycle arrest: CDK inhibitors up (+1), cyclins down (-1).
    "cell_cycle_arrest": Hallmark(
        "cell_cycle_arrest", +1,
        ("CDKN1A", "CDKN1B", "CDKN2A", "BTG2"),
        opposite_genes=("CCNA2", "CCNB1", "CCNE1"),
    ),
}


def filter_significant(lfc: dict[str, float], adj_p: dict[str, float] | None) -> dict[str, float]:
    """Zero out LFC for genes whose adjusted p-value is >= SIG_ADJ_P. Genes absent from adj_p are
    treated as significant (kept) unless explicitly provided."""
    if not adj_p:
        return dict(lfc)
    return {g: (v if adj_p.get(g, 0.0) < SIG_ADJ_P else 0.0) for g, v in lfc.items()}


def hallmark_score(lfc: dict[str, float], hallmark: Hallmark,
                   adj_p: dict[str, float] | None = None) -> float | None:
    """Compute one hallmark score from a gene->LFC map (LFC already at max dose).

    Missing genes contribute 0 to the sum but DO count toward |G_h| (the full curated set size),
    matching the paper's mean-over-gene-set definition. Returns None if the gene set is empty.
    """
    sig = filter_significant(lfc, adj_p)
    members = hallmark.genes + hallmark.opposite_genes
    if not members:
        return None
    total = 0.0
    for g in hallmark.genes:
        total += sig.get(g, 0.0)
    for g in hallmark.opposite_genes:
        total -= sig.get(g, 0.0)            # opposite-signed contribution
    score = (hallmark.direction * total) / len(members)
    return float(score)


def all_hallmark_scores(lfc: dict[str, float],
                        adj_p: dict[str, float] | None = None) -> dict[str, float | None]:
    """Compute all six hallmark scores for one drug-cell-line LFC profile."""
    return {name: hallmark_score(lfc, hm, adj_p) for name, hm in HALLMARKS.items()}

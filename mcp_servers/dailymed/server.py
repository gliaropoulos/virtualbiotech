"""DailyMed MCP server — drug-label safety content for the FDA Safety Officer agent.

Exposes structured SPL label sections (boxed/black-box warnings, warnings & cautions,
contraindications, adverse reactions) plus DailyMed SPL set-id discovery.
Run:  python -m mcp_servers.dailymed.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="dailymed",
    instructions=(
        "Retrieve FDA drug-label content. get_boxed_warning checks for a black-box warning; "
        "get_label_safety_sections returns warnings/contraindications/adverse reactions. Use to "
        "find label-level safety precedent for drugs sharing the target or mechanism."
    ),
)


def _env(summary: str, data, preview=None) -> dict:
    return {"summary": summary, "data": data, "preview": preview}


@mcp.tool
async def get_boxed_warning(
    drug: Annotated[str, Field(description="Generic or brand drug name, e.g. 'adalimumab'")],
) -> dict:
    """Check whether a drug carries an FDA boxed (black-box) warning and return its text if present.

    A boxed warning is the strongest labeling-level safety signal — highly relevant when assessing a
    target whose modulation is precedented by this drug.
    """
    label = client.first_label(await client.fetch_label(drug))
    if label is None:
        return _env(f"No FDA label found for '{drug}'.", None)
    boxed = client.has_boxed_warning(label)
    text = client.extract_sections(label, ["boxed_warning"]).get("boxed_warning")
    return _env(
        f"'{drug}': boxed warning = {boxed}.",
        {"drug": drug, "hasBoxedWarning": boxed, "boxedWarning": text,
         "names": client.label_openfda_names(label)},
        preview={"hasBoxedWarning": boxed},
    )


@mcp.tool
async def get_label_safety_sections(
    drug: Annotated[str, Field(description="Generic or brand drug name")],
) -> dict:
    """Return the key safety sections of a drug's FDA label: boxed warning, warnings & cautions,
    contraindications, and adverse reactions (flattened text).
    """
    label = client.first_label(await client.fetch_label(drug))
    if label is None:
        return _env(f"No FDA label found for '{drug}'.", None)
    sections = client.extract_sections(label)
    return _env(
        f"'{drug}': {len(sections)} safety section(s) present: {', '.join(sections) or 'none'}.",
        {"drug": drug, "sections": sections, "names": client.label_openfda_names(label)},
        preview={"sectionsPresent": list(sections)},
    )


@mcp.tool
async def find_dailymed_spls(
    drug: Annotated[str, Field(description="Drug name to look up in DailyMed")],
) -> dict:
    """Find DailyMed SPL documents (set-ids, titles, publication dates) for a drug name."""
    setids = client.parse_spl_setids(await client.find_spls(drug))
    return _env(f"{len(setids)} DailyMed SPL document(s) for '{drug}'.", setids, preview=setids[:5])


if __name__ == "__main__":  # pragma: no cover
    mcp.run()

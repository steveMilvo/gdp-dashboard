"""Optional LLM-assisted extraction of property data from free text.

The LLM's job is strictly **extraction**: turn a free-text property description
(e.g. an agent listing or a surveyor's site notes) into structured capital-works
and plant-and-equipment line items. It does NOT decide deductibility, rates, or
effective lives — those come from the deterministic statutory engine (`calc`) and
the ATO reference (`assets`).

Critically, everything the model proposes is run back through `validation` before
the app uses it, so any LLM value that conflicts with the tax rules is flagged
(and, where a lawful value exists, corrected). The law is always the source of
truth; the model can only suggest.

Requires the `anthropic` package and an `ANTHROPIC_API_KEY` in the environment.
If neither is present, `is_available()` returns False and the app falls back to
manual entry — the calculator works fully without the LLM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:  # pragma: no cover - import guard
    import anthropic
    from pydantic import BaseModel, Field
    _IMPORTS_OK = True
except Exception:  # pragma: no cover
    _IMPORTS_OK = False

from . import assets as asset_ref
from .calc import CapitalWorksItem, PlantAsset
from .validation import ValidationReport, validate_all

MODEL = "claude-opus-4-8"

_SYSTEM_PROMPT = """\
You extract structured data about an Australian residential investment property \
from free text, for a tax-depreciation estimator.

You ONLY extract facts that are stated or clearly implied. You do NOT decide \
whether anything is tax-deductible, you do NOT choose depreciation rates, and you \
do NOT decide effective lives — a separate deterministic engine applies the tax \
law (Division 43 capital works and Division 40 plant & equipment, including the \
2017 second-hand rules and the relevant ATO effective-life determination). Your \
output is validated against that engine, so do not guess at legal conclusions.

Extract:
- original_build_year: the year the original building was constructed, if stated.
- improvements: discrete capital works done AFTER the original build (renovations, \
  extensions, re-roofing, new kitchen/bathroom, decking, fencing, driveways, etc.). \
  Each needs a short description, the year the work was completed (best estimate if \
  a range is given), and the cost if stated (else 0).
- plant_assets: removable/mechanical assets (carpet, blinds, oven, dishwasher, \
  air-conditioner, hot water system, etc.). Each needs a description, cost if stated \
  (else 0), and is_new = true ONLY if the text says the investor newly bought/\
  installed it (otherwise false — assume it came with the property).

If a value is not present, omit it or use 0. Do not invent costs.
"""


if _IMPORTS_OK:

    class _Improvement(BaseModel):
        description: str
        completion_year: int
        cost: float = 0.0

    class _PlantAsset(BaseModel):
        description: str
        cost: float = 0.0
        is_new: bool = False
        # The model may suggest an effective life; it is cross-checked against the
        # ATO reference in validation and overridden where the reference exists.
        suggested_effective_life: Optional[float] = Field(default=None)

    class _Extraction(BaseModel):
        original_build_year: Optional[int] = None
        improvements: list[_Improvement] = Field(default_factory=list)
        plant_assets: list[_PlantAsset] = Field(default_factory=list)


@dataclass
class ExtractionResult:
    """LLM proposal, converted to engine objects and validated against the law."""

    original_build_year: Optional[int]
    capital_works: list[CapitalWorksItem]
    plant: list[PlantAsset]
    validation: ValidationReport
    raw_notes: str = ""


def is_available() -> bool:
    """True when the anthropic SDK and an API key are both present."""
    return _IMPORTS_OK and bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )


def extract_property_data(
    description: str,
    *,
    basis: str = "post_2026",
    investor_is_individual: bool = True,
    property_is_second_hand: bool = True,
    acquired_after_9may2017: bool = True,
    owner_start_year: int = 0,
    client: "anthropic.Anthropic | None" = None,
) -> ExtractionResult:
    """Use Claude to extract property data, then validate it against the tax rules.

    The returned `validation` report carries any conflicts between the model's
    proposal and the statutory engine. Effective lives are taken from the ATO
    reference table where the asset is recognised; the model's suggestion is only
    a fallback, and any disagreement is surfaced as a validation warning.
    """
    if not is_available():
        raise RuntimeError(
            "LLM extraction unavailable: install `anthropic` and set ANTHROPIC_API_KEY."
        )

    client = client or anthropic.Anthropic()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": description}],
        output_format=_Extraction,
    )
    data: _Extraction = response.parsed_output

    # Convert proposed capital works to engine objects (no legal judgement here).
    capital_works = [
        CapitalWorksItem(
            description=imp.description,
            completion_year=imp.completion_year,
            cost=imp.cost,
        )
        for imp in data.improvements
    ]

    # Convert proposed plant. Authoritative effective life comes from the ATO
    # reference; the model's suggestion is only used when nothing matches.
    plant: list[PlantAsset] = []
    for a in data.plant_assets:
        reference_life = asset_ref.effective_life_for(a.description, basis)
        life = reference_life if reference_life is not None else (
            a.suggested_effective_life or 0.0
        )
        plant.append(
            PlantAsset(
                description=a.description,
                cost=a.cost,
                effective_life=life,
                method="DV",
                start_year=owner_start_year,
                is_new=a.is_new,
            )
        )

    report = validate_all(
        capital_works,
        plant,
        basis=basis,
        investor_is_individual=investor_is_individual,
        property_is_second_hand=property_is_second_hand,
        acquired_after_9may2017=acquired_after_9may2017,
    )

    return ExtractionResult(
        original_build_year=data.original_build_year,
        capital_works=capital_works,
        plant=plant,
        validation=report,
    )

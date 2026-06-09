"""Cross-reference layer: validate proposed data against Australian tax law.

This is the guardrail for LLM-assisted input. The LLM (or a user) may *propose*
capital-works items and plant assets, but every proposed value is checked here
against the deterministic statutory rules in `calc` and the ATO effective-life
reference in `assets`. The law is always the source of truth; the LLM can never
silently override it.

Each check returns `ValidationIssue`s with a severity:

  * "error"   -- proposal conflicts with the law and must be corrected/blocked
                 (a `suggested_value` carries the lawful value where one exists).
  * "warning" -- proposal is implausible or deviates from the ATO reference and
                 should be reviewed.
  * "info"    -- a note the user should be aware of (e.g. immediate write-off).

Nothing here is tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from . import assets as asset_ref
from .calc import (
    IMMEDIATE_WRITEOFF_THRESHOLD,
    CapitalWorksItem,
    PlantAsset,
    div43_rate_and_life,
)

Severity = str  # "error" | "warning" | "info"

# Tolerance when comparing a proposed effective life to the ATO reference value.
LIFE_TOLERANCE_YEARS = 1.0


@dataclass
class ValidationIssue:
    severity: Severity
    field: str
    message: str
    suggested_value: Optional[Any] = None

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        tag = self.severity.upper()
        sv = "" if self.suggested_value is None else f" (suggested: {self.suggested_value})"
        return f"[{tag}] {self.field}: {self.message}{sv}"


@dataclass
class ValidationReport:
    issues: list[ValidationIssue]

    @property
    def ok(self) -> bool:
        """True when there are no blocking errors."""
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def extend(self, more: "ValidationReport") -> None:
        self.issues.extend(more.issues)


# ---------------------------------------------------------------------------
# Division 43 -- capital works
# ---------------------------------------------------------------------------

def validate_capital_works(
    item: CapitalWorksItem,
    *,
    current_year: int | None = None,
    purchase_year: int | None = None,
    claimed_deductible: bool | None = None,
    claimed_rate: float | None = None,
) -> ValidationReport:
    """Validate a proposed capital-works item against Division 43 rules.

    `claimed_deductible` / `claimed_rate` are optional assertions made by an LLM
    or user; when supplied they are checked against the statutory position and
    contradictions are raised as errors. `purchase_year` enables the initial-repair
    guardrail (a "repair" done at/before purchase is really a capital item).
    """
    issues: list[ValidationIssue] = []
    current_year = current_year or date.today().year

    if item.cost < 0:
        issues.append(ValidationIssue("error", "cost", "Cost cannot be negative.", 0.0))

    if item.completion_year > current_year:
        issues.append(
            ValidationIssue(
                "warning",
                "completion_year",
                f"Completion year {item.completion_year} is in the future.",
            )
        )

    # --- Repairs: immediate deduction, but watch for "initial repairs". ---
    if item.kind == "repair":
        if purchase_year is not None and item.completion_year <= purchase_year:
            issues.append(
                ValidationIssue(
                    "warning",
                    "kind",
                    (
                        f"A repair dated {item.completion_year} at/before purchase "
                        f"({purchase_year}) is likely an INITIAL REPAIR — fixing a "
                        "pre-existing defect is capital, NOT an immediate deduction. "
                        "Reclassify as 'initial_repair'."
                    ),
                    suggested_value="initial_repair",
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    "info",
                    "kind",
                    (
                        "Treated as a repair: 100% deductible in the year incurred "
                        "(must genuinely restore original condition, not improve)."
                    ),
                )
            )
        return ValidationReport(issues)

    # --- Initial repairs: capital, claimed via Div 43 only if structural. ---
    if item.kind == "initial_repair":
        issues.append(
            ValidationIssue(
                "info",
                "kind",
                (
                    "Initial repair: capital, not an immediate deduction. Modelled "
                    "as Division 43 (2.5%) on the assumption it is structural; a "
                    "non-structural initial repair instead goes to the CGT cost base."
                ),
            )
        )

    rate, life = div43_rate_and_life(item.completion_year, item.use)
    is_deductible = rate > 0 and life > 0

    # Core statutory gate: residential construction before 18 Jul 1985 is not
    # deductible at all.
    if not is_deductible:
        issues.append(
            ValidationIssue(
                "info",
                "completion_year",
                (
                    f"Construction in {item.completion_year} is not eligible for "
                    "Division 43 capital works (residential pre-18 Jul 1985). "
                    "Deduction is $0 for this item."
                ),
                suggested_value=0.0,
            )
        )

    # If an LLM/user claimed this is deductible but the law says it is not -> error.
    if claimed_deductible is True and not is_deductible:
        issues.append(
            ValidationIssue(
                "error",
                "deductible",
                (
                    "Proposed data claims a Division 43 deduction, but construction "
                    f"in {item.completion_year} is not eligible. Overriding to $0."
                ),
                suggested_value=False,
            )
        )

    # If a rate was asserted, it must match the statutory rate for that year.
    if claimed_rate is not None and is_deductible and abs(claimed_rate - rate) > 1e-9:
        issues.append(
            ValidationIssue(
                "error",
                "rate",
                (
                    f"Proposed rate {claimed_rate:.3%} does not match the statutory "
                    f"Division 43 rate for {item.completion_year}."
                ),
                suggested_value=rate,
            )
        )

    return ValidationReport(issues)


# ---------------------------------------------------------------------------
# Division 40 -- plant & equipment
# ---------------------------------------------------------------------------

def validate_plant_asset(
    asset: PlantAsset,
    *,
    basis: str = "post_2026",
    investor_is_individual: bool = True,
    property_is_second_hand: bool = True,
    acquired_after_9may2017: bool = True,
    claimed_deductible: bool | None = None,
) -> ValidationReport:
    """Validate a proposed plant asset against Division 40 rules and ATO lives."""
    issues: list[ValidationIssue] = []

    if asset.cost < 0:
        issues.append(ValidationIssue("error", "cost", "Asset cost cannot be negative.", 0.0))

    if asset.method not in ("DV", "PC"):
        issues.append(
            ValidationIssue(
                "error",
                "method",
                f"Unknown depreciation method '{asset.method}'.",
                suggested_value="DV",
            )
        )

    if asset.effective_life <= 0:
        issues.append(
            ValidationIssue("error", "effective_life", "Effective life must be positive.")
        )

    # Cross-check effective life against the ATO reference table.
    reference = asset_ref.effective_life_for(asset.description, basis)
    if reference is not None and asset.effective_life > 0:
        if abs(asset.effective_life - reference) > LIFE_TOLERANCE_YEARS:
            issues.append(
                ValidationIssue(
                    "warning",
                    "effective_life",
                    (
                        f"Proposed effective life {asset.effective_life:g}yr differs "
                        f"from the ATO reference ({reference:g}yr, {basis.replace('_', ' ')}) "
                        f"for '{reference and asset.description}'."
                    ),
                    suggested_value=reference,
                )
            )

    # 2017 second-hand restriction.
    eligible = asset.eligible(
        investor_is_individual=investor_is_individual,
        property_is_second_hand=property_is_second_hand,
        acquired_after_9may2017=acquired_after_9may2017,
    )
    if not eligible and asset.cost > 0 and asset.effective_life > 0:
        issues.append(
            ValidationIssue(
                "info",
                "is_new",
                (
                    "Second-hand asset in a second-hand residential property acquired "
                    "after 9 May 2017: not deductible for an individual investor "
                    "(2017 rules). Excluded from the claim."
                ),
                suggested_value=False,
            )
        )

    if claimed_deductible is True and not eligible:
        issues.append(
            ValidationIssue(
                "error",
                "deductible",
                (
                    "Proposed data claims a Division 40 deduction on a second-hand "
                    "asset that the 2017 rules exclude for an individual investor."
                ),
                suggested_value=False,
            )
        )

    if 0 < asset.cost <= IMMEDIATE_WRITEOFF_THRESHOLD:
        issues.append(
            ValidationIssue(
                "info",
                "cost",
                (
                    f"Asset costs ${asset.cost:,.0f} (<= ${IMMEDIATE_WRITEOFF_THRESHOLD:,.0f}); "
                    "eligible for an immediate write-off in year one rather than "
                    "depreciation over its effective life."
                ),
            )
        )

    return ValidationReport(issues)


def validate_all(
    capital_works: list[CapitalWorksItem],
    plant: list[PlantAsset],
    *,
    basis: str = "post_2026",
    investor_is_individual: bool = True,
    property_is_second_hand: bool = True,
    acquired_after_9may2017: bool = True,
    current_year: int | None = None,
    purchase_year: int | None = None,
) -> ValidationReport:
    """Validate a full proposed dataset (e.g. an LLM extraction) against the law."""
    report = ValidationReport([])
    for item in capital_works:
        report.extend(
            validate_capital_works(
                item, current_year=current_year, purchase_year=purchase_year
            )
        )
    for asset in plant:
        report.extend(
            validate_plant_asset(
                asset,
                basis=basis,
                investor_is_individual=investor_is_individual,
                property_is_second_hand=property_is_second_hand,
                acquired_after_9may2017=acquired_after_9may2017,
            )
        )
    return report

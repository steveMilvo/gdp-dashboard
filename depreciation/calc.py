"""Australian investment property tax depreciation engine.

Pure-Python calculation logic with no UI or framework dependencies, so the same
engine can power the Streamlit estimator, a future SaaS API for quantity
surveyors, and the unit tests.

Two deduction buckets are modelled, per the Income Tax Assessment Act 1997:

* Division 43 -- Capital works (the building structure and fixed improvements).
  Straight line ("prime cost") only. Eligibility and rate depend on when the
  *construction* of that item commenced, NOT when the property was bought.

* Division 40 -- Plant and equipment (removable / mechanical assets). Each asset
  declines over its ATO "effective life" using either the Diminishing Value
  (200%) or Prime Cost method. Subject to the 2017 second-hand restriction for
  individual investors.

IMPORTANT: This is an estimator. It uses financial-year (annual) granularity and
does not pro-rata part years. Real claims require a quantity surveyor's schedule.
Nothing here is tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

Method = Literal["DV", "PC"]

# Diminishing Value uses a 200% rate for assets first held from 10 May 2006.
DV_FACTOR = 2.0

# Individuals can immediately write off plant & equipment assets costing this or
# less when used to produce (non-business) rental income (s 40-80(2)).
IMMEDIATE_WRITEOFF_THRESHOLD = 300.0


# ---------------------------------------------------------------------------
# Division 43 -- Capital works
# ---------------------------------------------------------------------------

def div43_rate_and_life(completion_year: int, use: str = "residential") -> tuple[float, int]:
    """Return (annual_rate, life_years) for a Division 43 capital-works item.

    Based on the construction *commencement* year. Year granularity is used; the
    real statutory boundaries are exact dates (e.g. 15 Sep 1987), so items built
    in a boundary year should be confirmed against the actual date.

    Residential rental property:
        * on/after 1987 (15 Sep 1987)        -> 2.5% over 40 years
        * 1985 (18 Jul) .. 1986              -> 4.0% over 25 years
        * before 18 Jul 1985                 -> not deductible (0)

    Returns (0.0, 0) when no deduction is available.
    """
    if use == "residential":
        if completion_year >= 1987:
            return 0.025, 40
        if completion_year >= 1985:
            return 0.04, 25
        return 0.0, 0
    # Non-residential (e.g. structural improvements / industrial) generally
    # 2.5% from 1992; treated the same here for a conservative estimate.
    if completion_year >= 1992:
        return 0.025, 40
    if completion_year >= 1987:
        return 0.025, 40
    return 0.0, 0


# How a works item is treated for tax:
#   "capital_works"  -- structural improvement; Division 43 at 2.5%/40yr.
#   "repair"         -- restores original condition; 100% deductible in the year
#                       incurred (a revenue deduction, not depreciation).
#   "initial_repair" -- fixes a defect that existed at purchase; CAPITAL, not an
#                       immediate deduction. Structural initial repairs are
#                       claimed via Division 43; non-structural ones go to the CGT
#                       cost base (not modelled as a deduction here).
ItemKind = Literal["capital_works", "repair", "initial_repair"]


@dataclass
class CapitalWorksItem:
    """A building works component: capital works, a repair, or an initial repair.

    The original building is just one item; each renovation / extension done in a
    later year is its own item with its own 40-year (or 25-year) clock. `kind`
    selects the tax treatment (see ItemKind above).
    """

    description: str
    completion_year: int
    cost: float
    use: str = "residential"
    kind: ItemKind = "capital_works"

    @property
    def is_repair(self) -> bool:
        """An immediate (100% in-year) repair deduction."""
        return self.kind == "repair"

    def rate_and_life(self) -> tuple[float, int]:
        # Repairs are not a Division 43 capital-works claim.
        if self.is_repair:
            return 0.0, 0
        return div43_rate_and_life(self.completion_year, self.use)

    def annual_deduction(self) -> float:
        rate, _ = self.rate_and_life()
        return self.cost * rate

    def eligible(self) -> bool:
        if self.is_repair:
            return self.cost > 0
        rate, life = self.rate_and_life()
        return rate > 0 and life > 0

    def claim_end_year(self) -> Optional[int]:
        """Last financial year (inclusive) the item can be claimed, or None."""
        if self.is_repair:
            return self.completion_year
        _, life = self.rate_and_life()
        if life == 0:
            return None
        return self.completion_year + life - 1

    def deduction_for_year(self, year: int, owner_start_year: int) -> float:
        """Deduction available to *this owner* in a given financial year."""
        if not self.eligible():
            return 0.0

        if self.is_repair:
            # Whole cost deducted in the year incurred, only while income-producing.
            claim_year = max(self.completion_year, owner_start_year)
            return self.cost if year == claim_year else 0.0

        end = self.claim_end_year()
        if end is None:
            return 0.0
        # Claimable only while owned/income-producing and within the item's life.
        if year < max(self.completion_year, owner_start_year):
            return 0.0
        if year > end:
            return 0.0
        return self.annual_deduction()


# ---------------------------------------------------------------------------
# Division 40 -- Plant & equipment
# ---------------------------------------------------------------------------

@dataclass
class PlantAsset:
    """A Division 40 depreciating asset.

    `is_new` distinguishes assets the investor newly bought and installed (always
    claimable) from second-hand assets that came with the property (restricted by
    the 2017 rules for individuals -- see `eligible`).
    """

    description: str
    cost: float
    effective_life: float
    method: Method = "DV"
    start_year: int = 0           # financial year first used for income
    is_new: bool = True           # True = newly purchased & installed by owner

    def eligible(
        self,
        *,
        investor_is_individual: bool,
        property_is_second_hand: bool,
        acquired_after_9may2017: bool,
    ) -> bool:
        """Apply the 2017 Housing Tax Integrity second-hand restriction.

        An individual cannot deduct Division 40 on *previously used* (second-hand)
        assets in a second-hand residential property acquired after 9 May 2017.
        New assets the investor installs themselves remain claimable. Companies
        and other excluded entities are not affected.
        """
        if self.cost <= 0 or self.effective_life <= 0:
            return False
        if not investor_is_individual:
            return True
        if self.is_new:
            return True
        # Second-hand asset held by an individual:
        if property_is_second_hand and acquired_after_9may2017:
            return False
        return True

    def schedule(self, horizon_end_year: int) -> dict[int, float]:
        """Year -> deduction map from `start_year` to `horizon_end_year`.

        Assets at or below the immediate write-off threshold are fully deducted in
        the first year. Otherwise DV (200%) or Prime Cost is applied until the
        asset is written off or the horizon ends.
        """
        out: dict[int, float] = {}
        if self.cost <= 0 or self.effective_life <= 0:
            return out

        if self.cost <= IMMEDIATE_WRITEOFF_THRESHOLD:
            if self.start_year <= horizon_end_year:
                out[self.start_year] = self.cost
            return out

        if self.method == "PC":
            annual = self.cost / self.effective_life
            remaining = self.cost
            year = self.start_year
            while remaining > 1e-6 and year <= horizon_end_year:
                ded = min(annual, remaining)
                out[year] = out.get(year, 0.0) + ded
                remaining -= ded
                year += 1
        else:  # Diminishing Value (200%)
            rate = DV_FACTOR / self.effective_life
            opening = self.cost
            year = self.start_year
            # Cap iterations defensively (assets are written down to near zero).
            while opening > 1e-6 and year <= horizon_end_year and year < self.start_year + 200:
                ded = opening * rate
                if ded > opening:
                    ded = opening
                out[year] = out.get(year, 0.0) + ded
                opening -= ded
                year += 1
        return out


# ---------------------------------------------------------------------------
# Combined projection
# ---------------------------------------------------------------------------

@dataclass
class ProjectionInputs:
    capital_works: list[CapitalWorksItem] = field(default_factory=list)
    plant: list[PlantAsset] = field(default_factory=list)
    owner_start_year: int = 0          # first FY the property earns income
    horizon_years: int = 40
    investor_is_individual: bool = True
    property_is_second_hand: bool = True
    acquired_after_9may2017: bool = True
    marginal_tax_rate: float = 0.0     # e.g. 0.37 -> shows estimated tax saving


@dataclass
class YearRow:
    year: int
    div43: float
    div40: float
    repairs: float = 0.0   # immediate (100% in-year) repair deductions

    @property
    def total(self) -> float:
        return self.div43 + self.div40 + self.repairs


@dataclass
class ProjectionResult:
    rows: list[YearRow]
    marginal_tax_rate: float
    excluded_plant: list[PlantAsset]

    @property
    def total_div43(self) -> float:
        return sum(r.div43 for r in self.rows)

    @property
    def total_div40(self) -> float:
        return sum(r.div40 for r in self.rows)

    @property
    def total_repairs(self) -> float:
        return sum(r.repairs for r in self.rows)

    @property
    def grand_total(self) -> float:
        return self.total_div43 + self.total_div40 + self.total_repairs

    @property
    def year_one_total(self) -> float:
        return self.rows[0].total if self.rows else 0.0

    def first_n_total(self, n: int) -> float:
        return sum(r.total for r in self.rows[:n])

    @property
    def estimated_tax_saving_total(self) -> float:
        return self.grand_total * self.marginal_tax_rate


def build_projection(inputs: ProjectionInputs) -> ProjectionResult:
    """Build a year-by-year deduction projection from `owner_start_year`."""
    start = inputs.owner_start_year
    end = start + inputs.horizon_years - 1

    # Division 40 eligibility filter (2017 second-hand rule).
    eligible_plant: list[PlantAsset] = []
    excluded_plant: list[PlantAsset] = []
    for asset in inputs.plant:
        if asset.eligible(
            investor_is_individual=inputs.investor_is_individual,
            property_is_second_hand=inputs.property_is_second_hand,
            acquired_after_9may2017=inputs.acquired_after_9may2017,
        ):
            eligible_plant.append(asset)
        else:
            excluded_plant.append(asset)

    # Pre-compute each eligible asset's schedule.
    plant_schedules = [a.schedule(end) for a in eligible_plant]

    rows: list[YearRow] = []
    for year in range(start, end + 1):
        div43 = sum(
            item.deduction_for_year(year, start)
            for item in inputs.capital_works
            if not item.is_repair
        )
        repairs = sum(
            item.deduction_for_year(year, start)
            for item in inputs.capital_works
            if item.is_repair
        )
        div40 = sum(sched.get(year, 0.0) for sched in plant_schedules)
        rows.append(YearRow(year=year, div43=div43, div40=div40, repairs=repairs))

    return ProjectionResult(
        rows=rows,
        marginal_tax_rate=inputs.marginal_tax_rate,
        excluded_plant=excluded_plant,
    )

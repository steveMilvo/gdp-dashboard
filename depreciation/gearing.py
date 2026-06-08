"""Negative gearing / rental cash-flow engine.

Combines the depreciation projection with the cash costs of holding a rental
property to show the investor's tax position and after-tax holding cost.

Two regimes are modelled, reflecting the 2026 Budget measure:

* GRANDFATHERED (current law) -- properties purchased on/before 12 May 2026, and
  eligible new builds. A net rental loss can be offset against *other* income
  (salary etc.), giving an immediate tax saving. Negatively geared the usual way.

* RESTRICTED -- established residential property purchased after 7:30pm on
  12 May 2026. From 1 July 2027 a net rental loss can NO LONGER offset salary;
  it can only be applied against rental income or a capital gain on sale, with
  any excess carried forward. So a loss gives no immediate salary offset -- it
  accumulates as a carried-forward loss until there is rental profit (or a sale)
  to absorb it.

Depreciation (Division 43 + 40) is a *non-cash* deduction: it reduces the taxable
result without being a cash outflow, which is what often turns a property that is
cash-flow neutral into a tax loss. The engine keeps cash and tax effects separate.

Estimator only. Not tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The 12 May 2026 (7:30pm) purchase cut-off for grandfathering.
GRANDFATHER_CUTOFF_YEAR = 2026


@dataclass
class GearingInputs:
    annual_rent: float
    loan_interest: float            # annual deductible interest
    other_cash_expenses: float      # rates, insurance, maintenance, strata... (excl mgmt)
    marginal_tax_rate: float
    grandfathered: bool = True      # full offset against other income when True
    rent_growth: float = 0.0        # optional annual growth (e.g. 0.03)
    expense_growth: float = 0.0     # optional annual growth applied to fixed costs
    mgmt_pct: float = 0.0           # property management fee, as a fraction of rent
    # Optional stepped rent: financial year -> ANNUAL rent applying from that year
    # onward (a step function). When set, it overrides annual_rent + rent_growth.
    # Use this to model a rent change, e.g. {2024: 19_760, 2026: 46_800}.
    annual_rent_by_year: dict[int, float] | None = None


def stepped_value(breakpoints: dict[int, float], year: int) -> float:
    """Resolve a step-function value for `year` from {start_year: value} points.

    The value applying to a year is the one at the most recent start year on or
    before it. Years before the earliest breakpoint use the earliest value.
    """
    if not breakpoints:
        return 0.0
    applicable = [y for y in breakpoints if y <= year]
    key = max(applicable) if applicable else min(breakpoints)
    return breakpoints[key]


@dataclass
class GearingYear:
    year: int
    rent: float
    cash_expenses: float            # interest + other (the actual cash outgoings)
    depreciation: float             # non-cash deduction
    taxable_result: float           # rent - cash_expenses - depreciation
    offset_against_other_income: float  # portion of a loss that reduces salary etc.
    carried_forward_loss: float     # cumulative quarantined loss (restricted regime)
    tax_effect: float               # +ve = tax saved, -ve = extra tax payable
    pretax_cashflow: float          # rent - cash_expenses (depreciation excluded)
    aftertax_cashflow: float        # pretax_cashflow + tax_effect

    @property
    def aftertax_weekly(self) -> float:
        return self.aftertax_cashflow / 52.0


@dataclass
class GearingResult:
    rows: list[GearingYear] = field(default_factory=list)
    grandfathered: bool = True

    @property
    def year_one(self) -> GearingYear | None:
        return self.rows[0] if self.rows else None

    @property
    def total_tax_effect(self) -> float:
        return sum(r.tax_effect for r in self.rows)

    @property
    def final_carried_forward_loss(self) -> float:
        return self.rows[-1].carried_forward_loss if self.rows else 0.0


def is_grandfathered(purchase_year: int, is_new_build: bool = False) -> bool:
    """Default grandfathering status from the purchase year.

    Purchases on/before 12 May 2026 are grandfathered; eligible new builds are
    exempt regardless. Year granularity is used (the exact cut-off is 12 May
    2026), so a 2026 purchase should be confirmed against the actual date.
    """
    if is_new_build:
        return True
    return purchase_year <= GRANDFATHER_CUTOFF_YEAR


def project_gearing(
    inputs: GearingInputs,
    depreciation_by_year: dict[int, float],
) -> GearingResult:
    """Build a year-by-year negative-gearing projection.

    `depreciation_by_year` maps financial year -> total depreciation deduction
    (Division 43 + 40), typically from `calc.build_projection`.
    """
    rate = inputs.marginal_tax_rate
    result = GearingResult(grandfathered=inputs.grandfathered)
    carried = 0.0

    years = sorted(depreciation_by_year)
    for i, year in enumerate(years):
        if inputs.annual_rent_by_year:
            rent = stepped_value(inputs.annual_rent_by_year, year)
        else:
            rent = inputs.annual_rent * ((1 + inputs.rent_growth) ** i)
        fixed_costs = (inputs.loan_interest + inputs.other_cash_expenses) * (
            (1 + inputs.expense_growth) ** i
        )
        # Management fee tracks each year's rent.
        cash_expenses = fixed_costs + rent * inputs.mgmt_pct
        depreciation = depreciation_by_year[year]

        taxable_result = rent - cash_expenses - depreciation
        pretax_cashflow = rent - cash_expenses  # depreciation is non-cash

        if inputs.grandfathered:
            # Loss (or profit) flows straight to/against other income.
            offset = -taxable_result if taxable_result < 0 else 0.0
            tax_effect = -taxable_result * rate  # loss -> +saving; profit -> -tax
            # No carry-forward concept under the current regime.
        else:
            # Restricted: losses are quarantined; profits absorb carried losses.
            if taxable_result < 0:
                carried += -taxable_result
                offset = 0.0
                tax_effect = 0.0
            else:
                used = min(carried, taxable_result)
                carried -= used
                taxable_after = taxable_result - used
                offset = 0.0
                tax_effect = -taxable_after * rate

        aftertax_cashflow = pretax_cashflow + tax_effect

        result.rows.append(
            GearingYear(
                year=year,
                rent=rent,
                cash_expenses=cash_expenses,
                depreciation=depreciation,
                taxable_result=taxable_result,
                offset_against_other_income=offset,
                carried_forward_loss=carried,
                tax_effect=tax_effect,
                pretax_cashflow=pretax_cashflow,
                aftertax_cashflow=aftertax_cashflow,
            )
        )

    return result

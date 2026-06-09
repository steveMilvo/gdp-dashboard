"""Policy-scenario comparison: rate a prospective buy under different regimes.

The same property is run through several tax-policy regimes so an investor can
see how the after-tax outcome changes — in particular, how today's rules compare
with the way negative gearing and CGT *used to* work, and with a plausible future
reform if a government tightened them again.

Three reference regimes are provided (the assumptions are configurable):

* OLD / CURRENT (grandfathered) -- full negative gearing (a rental loss offsets
  salary) + the 50% CGT discount. This is what established residential property
  bought on/before 12 May 2026 keeps, and how the system has worked for decades.

* 2026 RESTRICTION -- established residential bought after 12 May 2026: a rental
  loss no longer offsets salary (it is quarantined and carried forward against
  future rental income or the capital gain), but the 50% CGT discount remains.

* LIKELY FUTURE REFORM -- a plausible tightening modelled on the ALP 2016/2019
  policy: negative gearing limited to new builds (so established property loses
  the salary offset) AND the CGT discount halved from 50% to 25%. This is a
  SPECULATIVE assumption, not law — it is fully configurable.

For each regime the engine computes the holding-period after-tax cash flow and
the CGT on sale (with the regime's discount, and applying any carried-forward
losses against the gain), then a single net result so the regimes can be ranked.

Leverage, loan principal, selling costs and many other factors are out of scope,
so the absolute figures are indicative — the *differences between regimes* are
the point. Estimator only. Not tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from depreciation.costbase import PurchaseDetails, compute_cost_base
from depreciation.gearing import GearingInputs, project_gearing


@dataclass(frozen=True)
class PolicyScenario:
    name: str
    full_negative_gearing: bool  # True = a rental loss offsets other income (salary)
    cgt_discount: float          # proportion of gain removed before tax (0.5 = 50%)
    description: str = ""


# Reference regimes. cgt_discount is the *discount* fraction (0.5 => 50% off).
OLD_RULES = PolicyScenario(
    name="Old / current rules",
    full_negative_gearing=True,
    cgt_discount=0.5,
    description="Full negative gearing (loss offsets salary) + 50% CGT discount.",
)
RESTRICTION_2026 = PolicyScenario(
    name="2026 restriction",
    full_negative_gearing=False,
    cgt_discount=0.5,
    description="Loss quarantined (no salary offset), 50% CGT discount retained.",
)
LIKELY_REFORM = PolicyScenario(
    name="Likely future reform",
    full_negative_gearing=False,
    cgt_discount=0.25,
    description="Negative gearing limited to new builds + CGT discount halved to 25%.",
)

REFERENCE_SCENARIOS = (OLD_RULES, RESTRICTION_2026, LIKELY_REFORM)


@dataclass
class ScenarioResult:
    scenario: PolicyScenario
    hold_years: int
    total_pretax_cashflow: float       # sum of rent - cash costs over the hold
    total_holding_tax_benefit: float   # sum of tax effects realised while holding
    total_aftertax_cashflow: float     # pretax cash flow + holding tax benefit
    carried_forward_at_sale: float     # quarantined losses remaining at sale
    gross_capital_gain: float          # sale price - adjusted cost base at sale
    cgt_payable: float
    net_capital_gain_after_cgt: float
    net_result: float                  # after-tax cash flow + net capital gain
    annualised_return_on_equity: float # net_result / equity, annualised (rough)

    @property
    def rating(self) -> str:
        return rate_return(self.annualised_return_on_equity)


def rate_return(annualised: float) -> str:
    """Coarse qualitative grade for an annualised after-tax return on equity."""
    if annualised >= 0.12:
        return "Excellent"
    if annualised >= 0.08:
        return "Strong"
    if annualised >= 0.04:
        return "Moderate"
    if annualised >= 0.0:
        return "Weak"
    return "Negative"


def evaluate_scenario(
    scenario: PolicyScenario,
    *,
    gearing_inputs: GearingInputs,
    depreciation_by_year: dict[int, float],
    div43_by_year: dict[int, float],
    purchase: PurchaseDetails,
    capital_works_items: list,
    sale_year: int,
    sale_price: float,
    marginal_rate: float,
    is_individual: bool = True,
    held_over_12_months: bool = True,
    initial_equity: float = 0.0,
) -> ScenarioResult:
    """Run one policy regime end-to-end for a single property.

    `depreciation_by_year` is the full deduction per year (Div 43 + 40 + repairs)
    used by the gearing model; `div43_by_year` is the Division-43-only portion,
    which is what reduces the CGT cost base.
    """
    # Force this regime's negative-gearing treatment (ignore commercial here so
    # the comparison is a clean residential like-for-like).
    g_inputs = replace(
        gearing_inputs,
        grandfathered=scenario.full_negative_gearing,
        commercial=False,
    )
    g = project_gearing(g_inputs, depreciation_by_year)

    held = [r for r in g.rows if r.year <= sale_year]
    total_pretax = sum(r.pretax_cashflow for r in held)
    total_tax_benefit = sum(r.tax_effect for r in held)
    total_aftertax = total_pretax + total_tax_benefit
    carried_at_sale = held[-1].carried_forward_loss if held else 0.0

    # Cost base at the sale year: reduced by Division 43 claimed up to the sale.
    div43_to_sale = sum(v for y, v in div43_by_year.items() if y <= sale_year)
    cb = compute_cost_base(
        purchase,
        capital_works_items=capital_works_items,
        div43_deductions_taken=div43_to_sale,
    )
    gross_gain = cb.estimated_gain(sale_price)
    cgt = cb.cgt_payable(
        sale_price,
        marginal_rate,
        held_over_12_months=held_over_12_months,
        is_individual=is_individual,
        cgt_discount=scenario.cgt_discount,
        carried_forward_loss=carried_at_sale,
    )
    net_gain_after_cgt = gross_gain - cgt
    net_result = total_aftertax + net_gain_after_cgt

    hold_years = max(1, len(held))
    equity = initial_equity if initial_equity > 0 else 1.0
    total_return = net_result / equity
    # Rough annualisation; guard against a wipe-out base.
    if total_return > -1.0:
        annualised = (1.0 + total_return) ** (1.0 / hold_years) - 1.0
    else:
        annualised = total_return / hold_years

    return ScenarioResult(
        scenario=scenario,
        hold_years=hold_years,
        total_pretax_cashflow=total_pretax,
        total_holding_tax_benefit=total_tax_benefit,
        total_aftertax_cashflow=total_aftertax,
        carried_forward_at_sale=carried_at_sale,
        gross_capital_gain=gross_gain,
        cgt_payable=cgt,
        net_capital_gain_after_cgt=net_gain_after_cgt,
        net_result=net_result,
        annualised_return_on_equity=annualised,
    )


def compare_scenarios(scenarios=REFERENCE_SCENARIOS, **kwargs) -> list[ScenarioResult]:
    """Evaluate several regimes for the same property, in the given order."""
    return [evaluate_scenario(s, **kwargs) for s in scenarios]

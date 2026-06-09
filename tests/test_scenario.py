"""Tests for the policy-scenario comparison engine.

Verifies that the same property produces different after-tax outcomes under the
old/current rules, the 2026 restriction, and a likely future reform, and that
the differences move in the directions the tax law implies.
"""

import math

from depreciation.costbase import PurchaseDetails
from depreciation.gearing import GearingInputs
from depreciation.scenario import (
    LIKELY_REFORM,
    OLD_RULES,
    RESTRICTION_2026,
    PolicyScenario,
    compare_scenarios,
    evaluate_scenario,
    rate_return,
)


def _setup(*, sale_year=2034, sale_price=1_050_000):
    """A negatively geared property: rent < interest + costs + depreciation."""
    years = list(range(2024, 2024 + 15))
    # Flat $25k/yr depreciation, of which $10k is Division 43 (cost-base reducing).
    depreciation_by_year = {y: 25_000.0 for y in years}
    div43_by_year = {y: 10_000.0 for y in years}
    gearing_inputs = GearingInputs(
        annual_rent=26_000.0,          # $500/wk
        loan_interest=37_000.0,        # heavy interest -> a loss
        other_cash_expenses=8_000.0,
        marginal_tax_rate=0.37,
    )
    purchase = PurchaseDetails(
        purchase_price=700_000, land_value=300_000, stamp_duty=30_000, legal_fees=2_000
    )
    common = dict(
        gearing_inputs=gearing_inputs,
        depreciation_by_year=depreciation_by_year,
        div43_by_year=div43_by_year,
        purchase=purchase,
        capital_works_items=[],
        sale_year=sale_year,
        sale_price=sale_price,
        marginal_rate=0.37,
        is_individual=True,
        held_over_12_months=True,
        initial_equity=150_000.0,
    )
    return common


def _setup_positive(*, sale_year=2034, sale_price=1_050_000):
    """A mildly positive property so carried losses don't dominate CGT.

    Used to isolate the *CGT discount* effect between regimes: with no carried
    losses, the only thing distinguishing regimes at sale is the discount.
    """
    years = list(range(2024, 2024 + 15))
    depreciation_by_year = {y: 8_000.0 for y in years}
    div43_by_year = {y: 5_000.0 for y in years}
    gearing_inputs = GearingInputs(
        annual_rent=45_000.0,
        loan_interest=20_000.0,
        other_cash_expenses=7_000.0,   # taxable ~ +10k/yr -> no carried loss
        marginal_tax_rate=0.37,
    )
    purchase = PurchaseDetails(
        purchase_price=700_000, land_value=300_000, stamp_duty=30_000, legal_fees=2_000
    )
    return dict(
        gearing_inputs=gearing_inputs,
        depreciation_by_year=depreciation_by_year,
        div43_by_year=div43_by_year,
        purchase=purchase,
        capital_works_items=[],
        sale_year=sale_year,
        sale_price=sale_price,
        marginal_rate=0.37,
        is_individual=True,
        held_over_12_months=True,
        initial_equity=150_000.0,
    )


# ---------------------------------------------------------------------------
# Holding-period behaviour
# ---------------------------------------------------------------------------

def test_old_rules_give_immediate_salary_offset():
    common = _setup()
    old = evaluate_scenario(OLD_RULES, **common)
    # Full negative gearing: the rental loss saves tax every year -> positive benefit.
    assert old.total_holding_tax_benefit > 0
    assert old.carried_forward_at_sale == 0.0


def test_restriction_quarantines_the_loss_during_holding():
    common = _setup()
    restricted = evaluate_scenario(RESTRICTION_2026, **common)
    # No salary offset while holding: holding tax benefit is zero and the loss
    # is carried forward to the sale.
    assert math.isclose(restricted.total_holding_tax_benefit, 0.0)
    assert restricted.carried_forward_at_sale > 0


def test_old_beats_restriction_on_aftertax_cashflow():
    common = _setup()
    old = evaluate_scenario(OLD_RULES, **common)
    restricted = evaluate_scenario(RESTRICTION_2026, **common)
    # Immediate offset is worth more than carrying the loss forward.
    assert old.total_aftertax_cashflow > restricted.total_aftertax_cashflow


# ---------------------------------------------------------------------------
# CGT behaviour
# ---------------------------------------------------------------------------

def test_carried_losses_reduce_cgt_under_restriction():
    common = _setup()
    old = evaluate_scenario(OLD_RULES, **common)
    restricted = evaluate_scenario(RESTRICTION_2026, **common)
    # Restriction carries losses into the sale, reducing the taxable gain, so its
    # CGT is lower than the old-rules CGT (same 50% discount in both).
    assert restricted.cgt_payable < old.cgt_payable


def test_future_reform_has_higher_cgt_than_old_rules():
    # Use a positively geared property so no carried losses shelter the gain;
    # the only difference at sale is then the CGT discount.
    common = _setup_positive()
    old = evaluate_scenario(OLD_RULES, **common)
    reform = evaluate_scenario(LIKELY_REFORM, **common)
    # Reform halves the CGT discount (50% -> 25%), so more of the gain is taxed.
    assert reform.cgt_payable > old.cgt_payable


def test_heavy_carried_losses_can_eliminate_cgt_under_restriction():
    # A heavily negatively geared property accumulates quarantined losses that
    # offset the capital gain — under the restriction this can wipe out CGT.
    common = _setup()
    restricted = evaluate_scenario(RESTRICTION_2026, **common)
    assert restricted.carried_forward_at_sale > restricted.gross_capital_gain
    assert restricted.cgt_payable == 0.0


# ---------------------------------------------------------------------------
# Net result / ranking
# ---------------------------------------------------------------------------

def test_old_rules_are_the_best_net_result():
    common = _setup()
    results = compare_scenarios(**common)
    by_name = {r.scenario.name: r for r in results}
    old = by_name["Old / current rules"]
    restricted = by_name["2026 restriction"]
    reform = by_name["Likely future reform"]
    # Old rules are the most generous, the reform the least.
    assert old.net_result >= restricted.net_result >= reform.net_result


def test_compare_scenarios_returns_in_order():
    common = _setup()
    results = compare_scenarios(**common)
    assert [r.scenario for r in results] == [OLD_RULES, RESTRICTION_2026, LIKELY_REFORM]
    assert all(r.hold_years > 1 for r in results)


def test_no_capital_gain_means_no_cgt():
    common = _setup(sale_price=600_000)  # sells below cost base -> capital loss
    old = evaluate_scenario(OLD_RULES, **common)
    assert old.gross_capital_gain < 0
    assert old.cgt_payable == 0.0


# ---------------------------------------------------------------------------
# Rating helper
# ---------------------------------------------------------------------------

def test_rate_return_bands():
    assert rate_return(0.15) == "Excellent"
    assert rate_return(0.09) == "Strong"
    assert rate_return(0.05) == "Moderate"
    assert rate_return(0.01) == "Weak"
    assert rate_return(-0.02) == "Negative"


def test_custom_scenario_with_no_discount():
    common = _setup_positive()
    no_discount = PolicyScenario("No discount", full_negative_gearing=False, cgt_discount=0.0)
    res = evaluate_scenario(no_discount, **common)
    reform = evaluate_scenario(LIKELY_REFORM, **common)
    # Removing the discount entirely taxes more gain than the 25% reform discount.
    assert res.cgt_payable > reform.cgt_payable

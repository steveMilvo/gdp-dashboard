"""Tests for the negative-gearing / cash-flow engine."""

import math

from depreciation.gearing import (
    GRANDFATHER_CUTOFF_YEAR,
    GearingInputs,
    full_offset_available,
    is_grandfathered,
    project_gearing,
    stepped_value,
)


def test_grandfathering_by_purchase_year():
    assert is_grandfathered(2024) is True            # pre-cutoff -> grandfathered
    assert is_grandfathered(2026) is True            # on/before 12 May 2026 (year level)
    assert is_grandfathered(2027) is False           # established, post-cutoff
    assert is_grandfathered(2028, is_new_build=True) is True  # new builds exempt


def _depr(years, amount):
    return {y: amount for y in years}


def test_grandfathered_loss_offsets_other_income():
    # Rent 26k, interest 30k, other 5k, depreciation 8k -> taxable loss of 17k.
    inputs = GearingInputs(
        annual_rent=26_000,
        loan_interest=30_000,
        other_cash_expenses=5_000,
        marginal_tax_rate=0.37,
        grandfathered=True,
    )
    res = project_gearing(inputs, _depr([2024], 8_000))
    yr = res.rows[0]
    assert math.isclose(yr.taxable_result, -17_000)
    # Whole loss offsets salary -> tax saving = 17k * 37%.
    assert math.isclose(yr.tax_effect, 17_000 * 0.37)
    assert math.isclose(yr.offset_against_other_income, 17_000)
    # Pre-tax cash outflow excludes the non-cash depreciation: 26k - 35k = -9k.
    assert math.isclose(yr.pretax_cashflow, -9_000)
    assert math.isclose(yr.aftertax_cashflow, -9_000 + 17_000 * 0.37)
    assert yr.carried_forward_loss == 0.0


def test_restricted_loss_is_quarantined_and_carried_forward():
    inputs = GearingInputs(
        annual_rent=26_000,
        loan_interest=30_000,
        other_cash_expenses=5_000,
        marginal_tax_rate=0.37,
        grandfathered=False,
    )
    res = project_gearing(inputs, _depr([2027, 2028], 8_000))
    y1 = res.rows[0]
    # No immediate salary offset; the 17k loss is carried forward.
    assert y1.tax_effect == 0.0
    assert y1.offset_against_other_income == 0.0
    assert math.isclose(y1.carried_forward_loss, 17_000)
    # Year two adds another 17k loss -> 34k carried forward.
    assert math.isclose(res.rows[1].carried_forward_loss, 34_000)


def test_restricted_profit_absorbs_carried_loss_before_tax():
    inputs = GearingInputs(
        annual_rent=60_000,          # high rent -> a taxable profit in year 2
        loan_interest=10_000,
        other_cash_expenses=5_000,
        marginal_tax_rate=0.37,
        grandfathered=False,
    )
    # Year 1: big depreciation creates a loss; Year 2: small depreciation -> profit.
    res = project_gearing(inputs, {2027: 60_000, 2028: 5_000})
    y1, y2 = res.rows
    # Y1 taxable: 60k - 15k - 60k = -15k loss, carried forward, no tax.
    assert math.isclose(y1.taxable_result, -15_000)
    assert y1.tax_effect == 0.0
    assert math.isclose(y1.carried_forward_loss, 15_000)
    # Y2 taxable: 60k - 15k - 5k = +40k profit; 15k carried loss absorbs first,
    # leaving 25k taxable -> tax payable of 25k * 37%.
    assert math.isclose(y2.taxable_result, 40_000)
    assert math.isclose(y2.tax_effect, -25_000 * 0.37)
    assert y2.carried_forward_loss == 0.0


def test_commercial_is_exempt_from_restriction():
    # Post-cutoff purchase would normally be restricted...
    assert full_offset_available(2028, commercial=False) is False
    # ...but commercial premises keep the full offset regardless of date.
    assert full_offset_available(2028, commercial=True) is True


def test_commercial_loss_offsets_other_income_even_when_not_grandfathered():
    inputs = GearingInputs(
        annual_rent=46_800,             # $900/wk boarding house
        loan_interest=30_000,
        other_cash_expenses=20_000,
        marginal_tax_rate=0.37,
        grandfathered=False,            # would be restricted if residential
        commercial=True,                # but it's commercial residential -> exempt
    )
    res = project_gearing(inputs, {2028: 8_000})
    yr = res.rows[0]
    # Taxable: 46.8k - 50k - 8k = -11.2k loss; commercial -> full salary offset.
    assert math.isclose(yr.taxable_result, -11_200)
    assert math.isclose(yr.tax_effect, 11_200 * 0.37)
    assert yr.carried_forward_loss == 0.0


def test_stepped_value_step_function():
    points = {2024: 380 * 52, 2026: 900 * 52}
    assert stepped_value(points, 2023) == 380 * 52   # before first -> earliest
    assert stepped_value(points, 2024) == 380 * 52
    assert stepped_value(points, 2025) == 380 * 52    # still in first period
    assert stepped_value(points, 2026) == 900 * 52    # switches at the boarding-house year
    assert stepped_value(points, 2030) == 900 * 52    # carries forward


def test_stepped_rent_changes_taxable_result_across_years():
    # $380/wk to 2025, then $900/wk (boarding house) from 2026.
    inputs = GearingInputs(
        annual_rent=0,  # ignored when annual_rent_by_year is set
        loan_interest=30_000,
        other_cash_expenses=5_000,
        marginal_tax_rate=0.37,
        grandfathered=True,
        mgmt_pct=0.07,
        annual_rent_by_year={2024: 380 * 52, 2026: 900 * 52},
    )
    res = project_gearing(inputs, {2024: 8_000, 2025: 7_000, 2026: 6_000})
    y2024, y2025, y2026 = res.rows
    assert math.isclose(y2024.rent, 380 * 52)
    assert math.isclose(y2025.rent, 380 * 52)
    assert math.isclose(y2026.rent, 900 * 52)
    # 2024 loss (low rent) -> tax saving; 2026 with $900/wk should be far better off.
    assert y2026.aftertax_cashflow > y2024.aftertax_cashflow
    # Management fee tracks rent: 7% of the higher 2026 rent.
    assert math.isclose(y2026.cash_expenses, 30_000 + 5_000 + 900 * 52 * 0.07)


def test_grandfathered_positive_geared_pays_tax():
    inputs = GearingInputs(
        annual_rent=40_000,
        loan_interest=10_000,
        other_cash_expenses=5_000,
        marginal_tax_rate=0.37,
        grandfathered=True,
    )
    res = project_gearing(inputs, _depr([2024], 5_000))
    yr = res.rows[0]
    # Taxable: 40k - 15k - 5k = +20k profit -> extra tax of 20k * 37%.
    assert math.isclose(yr.taxable_result, 20_000)
    assert math.isclose(yr.tax_effect, -20_000 * 0.37)

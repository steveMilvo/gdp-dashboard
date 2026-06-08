"""Tests for the purchase price / cost base / CGT engine."""

import math

from depreciation.calc import CapitalWorksItem
from depreciation.costbase import PurchaseDetails, compute_cost_base


def _purchase(price=700_000, land=280_000, stamp=28_000, legal=2_000):
    return PurchaseDetails(
        purchase_price=price,
        land_value=land,
        stamp_duty=stamp,
        legal_fees=legal,
    )


def test_land_building_split():
    p = _purchase(700_000, 280_000)
    assert math.isclose(p.building_value, 420_000)
    assert math.isclose(p.land_pct, 0.4)
    assert math.isclose(p.building_pct, 0.6)


def test_element1_and_2_includes_acquisition_costs():
    p = _purchase(700_000, 280_000, stamp=28_000, legal=2_000)
    assert math.isclose(p.element1_and_2, 730_000)


def test_cost_base_adds_initial_repairs():
    p = _purchase()
    items = [
        CapitalWorksItem("Restumping", 2024, 30_000, kind="initial_repair"),
        CapitalWorksItem("Kitchen reno", 2008, 25_000, kind="capital_works"),
    ]
    cb = compute_cost_base(p, capital_works_items=items, div43_deductions_taken=0)
    # Initial repair ($30k) added to cost base; capital works not added (Div 43).
    assert math.isclose(cb.capital_additions, 30_000)
    assert math.isclose(cb.adjusted_cost_base, 730_000 + 30_000)


def test_div43_claimed_reduces_cost_base():
    p = _purchase()
    cb = compute_cost_base(p, capital_works_items=[], div43_deductions_taken=15_000)
    assert math.isclose(cb.adjusted_cost_base, 730_000 - 15_000)


def test_estimated_gain_and_cgt():
    p = _purchase()
    cb = compute_cost_base(p, capital_works_items=[], div43_deductions_taken=20_000)
    # Cost base: 730k - 20k = 710k. Sale at 950k -> gain 240k.
    assert math.isclose(cb.estimated_gain(950_000), 240_000)
    # Individual held > 12m: 50% discount -> 120k taxable at 37%.
    assert math.isclose(cb.cgt_payable(950_000, 0.37), 120_000 * 0.37)
    # No discount for company or short hold.
    assert math.isclose(cb.cgt_payable(950_000, 0.37, is_individual=False), 240_000 * 0.37)


def test_no_cgt_on_loss():
    p = _purchase(700_000, 280_000, 28_000, 2_000)
    cb = compute_cost_base(p, capital_works_items=[], div43_deductions_taken=0)
    assert cb.cgt_payable(600_000, 0.37) == 0.0

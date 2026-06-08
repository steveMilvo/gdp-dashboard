"""Tests for ongoing-maintenance expense flows (Section 3 of the app).

Covers two scenarios:
  1. Repair / maintenance → immediate 100% deduction in the year incurred
     (kind="repair" on a CapitalWorksItem).
  2. Replaced asset → new Div 40 plant from the replacement year, not
     subject to the 2017 second-hand restriction (is_new=True).
"""

import math

from depreciation.calc import (
    CapitalWorksItem,
    PlantAsset,
    ProjectionInputs,
    build_projection,
)


def _repair(desc="Plumbing — blocked pipes", year=2026, cost=1_200):
    return CapitalWorksItem(desc, year, cost, kind="repair")


def _replacement(desc="Hot water system (new)", cost=2_800, start_year=2026):
    return PlantAsset(desc, cost, effective_life=12, method="DV", start_year=start_year, is_new=True)


# ---------------------------------------------------------------------------
# Repair / maintenance
# ---------------------------------------------------------------------------

def test_repair_deducted_in_year_incurred():
    item = _repair(year=2026, cost=1_200)
    # Full cost in 2026 only (income_start = 2024, so 2026 qualifies).
    assert item.deduction_for_year(2026, 2024) == 1_200.0
    assert item.deduction_for_year(2027, 2024) == 0.0


def test_repair_appears_in_repairs_bucket_not_div43():
    inputs = ProjectionInputs(
        capital_works=[_repair(year=2026, cost=1_200)],
        plant=[],
        owner_start_year=2024,
        horizon_years=5,
    )
    result = build_projection(inputs)
    yr_2026 = next(r for r in result.rows if r.year == 2026)
    yr_2027 = next(r for r in result.rows if r.year == 2027)
    assert math.isclose(yr_2026.repairs, 1_200.0)
    assert yr_2026.div43 == 0.0
    assert yr_2027.repairs == 0.0


def test_multiple_repairs_in_same_year():
    inputs = ProjectionInputs(
        capital_works=[
            _repair("Plumbing", 2026, 1_200),
            _repair("Repaint fence", 2026, 800),
        ],
        plant=[],
        owner_start_year=2024,
        horizon_years=5,
    )
    result = build_projection(inputs)
    yr_2026 = next(r for r in result.rows if r.year == 2026)
    assert math.isclose(yr_2026.repairs, 2_000.0)


# ---------------------------------------------------------------------------
# Replaced asset — Div 40 plant from replacement year
# ---------------------------------------------------------------------------

def test_replaced_asset_depreciates_from_replacement_year():
    asset = _replacement(cost=2_800, start_year=2026)
    sched = asset.schedule(2100)
    # DV rate: 200% / 12 = 16.67% -> ~467 in first year
    assert 2026 in sched
    assert math.isclose(sched[2026], 2_800 * (2.0 / 12), rel_tol=1e-6)
    assert 2025 not in sched


def test_replaced_asset_is_new_so_not_excluded_by_2017_rule():
    asset = _replacement(cost=2_800, start_year=2026)
    # Even though the *property* is second-hand, the *asset* is new → eligible.
    assert asset.eligible(
        investor_is_individual=True,
        property_is_second_hand=True,
        acquired_after_9may2017=True,
    )


def test_replaced_asset_flows_into_projection_div40():
    inputs = ProjectionInputs(
        capital_works=[],
        plant=[_replacement(cost=2_800, start_year=2026)],
        owner_start_year=2024,
        horizon_years=5,
        investor_is_individual=True,
        property_is_second_hand=True,
        acquired_after_9may2017=True,
    )
    result = build_projection(inputs)
    assert not result.excluded_plant  # new asset must not be excluded
    yr_2026 = next(r for r in result.rows if r.year == 2026)
    expected = 2_800 * (2.0 / 12)
    assert math.isclose(yr_2026.div40, expected, rel_tol=1e-6)
    assert yr_2026.repairs == 0.0


# ---------------------------------------------------------------------------
# Combined: repair + replaced asset in the same projection
# ---------------------------------------------------------------------------

def test_combined_repair_and_replacement_in_same_year():
    inputs = ProjectionInputs(
        capital_works=[_repair("Plumbing", 2026, 1_200)],
        plant=[_replacement("Hot water system", 2_800, 2026)],
        owner_start_year=2024,
        horizon_years=5,
        investor_is_individual=True,
        property_is_second_hand=True,
        acquired_after_9may2017=True,
    )
    result = build_projection(inputs)
    yr_2026 = next(r for r in result.rows if r.year == 2026)
    expected_div40 = 2_800 * (2.0 / 12)
    assert math.isclose(yr_2026.repairs, 1_200.0)
    assert math.isclose(yr_2026.div40, expected_div40, rel_tol=1e-6)
    assert math.isclose(yr_2026.total, 1_200.0 + expected_div40, rel_tol=1e-6)

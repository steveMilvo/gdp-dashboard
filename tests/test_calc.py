"""Tests for the depreciation engine and the tax-rule validation layer."""

import math

from depreciation.calc import (
    CapitalWorksItem,
    PlantAsset,
    ProjectionInputs,
    build_projection,
    div43_rate_and_life,
)
from depreciation.validation import validate_capital_works, validate_plant_asset


# ---------------------------------------------------------------------------
# Division 43 — eligibility by construction date
# ---------------------------------------------------------------------------

def test_div43_pre_1985_not_deductible():
    rate, life = div43_rate_and_life(1930)
    assert rate == 0.0 and life == 0


def test_div43_1985_to_1986_four_percent():
    rate, life = div43_rate_and_life(1986)
    assert rate == 0.04 and life == 25


def test_div43_post_1987_two_and_half_percent():
    rate, life = div43_rate_and_life(2008)
    assert rate == 0.025 and life == 40


def test_1930_house_original_structure_yields_nothing():
    item = CapitalWorksItem("Original building", 1930, 200_000)
    assert not item.eligible()
    assert item.deduction_for_year(2024, 2024) == 0.0


def test_post_1987_renovation_on_old_house_is_claimable():
    reno = CapitalWorksItem("Kitchen reno", 2008, 30_000)
    assert reno.eligible()
    # 2.5% of 30k = 750/yr, claimable 40 years from 2008 -> through 2047.
    assert math.isclose(reno.deduction_for_year(2024, 2024), 750.0)
    assert reno.deduction_for_year(2048, 2024) == 0.0  # past 40-year life


def test_capital_works_only_claimable_once_owned():
    reno = CapitalWorksItem("Reno", 2008, 30_000)
    # Owner started renting in 2024 — no deduction for 2010 even though in-life.
    assert reno.deduction_for_year(2010, 2024) == 0.0


# ---------------------------------------------------------------------------
# Division 40 — depreciation methods and the 2017 rule
# ---------------------------------------------------------------------------

def test_prime_cost_schedule_sums_to_cost():
    asset = PlantAsset("Carpet", 8000, effective_life=8, method="PC", start_year=2024)
    sched = asset.schedule(2100)
    assert math.isclose(sum(sched.values()), 8000.0)
    assert math.isclose(sched[2024], 1000.0)  # 8000 / 8


def test_diminishing_value_first_year():
    asset = PlantAsset("Carpet", 8000, effective_life=8, method="DV", start_year=2024)
    sched = asset.schedule(2100)
    # DV rate 200%/8 = 25% -> 2000 in year one.
    assert math.isclose(sched[2024], 2000.0)
    assert sum(sched.values()) < 8000.0  # never fully writes off, approaches it


def test_immediate_writeoff_under_300():
    asset = PlantAsset("Smoke alarm", 250, effective_life=6, method="DV", start_year=2024)
    sched = asset.schedule(2100)
    assert sched == {2024: 250.0}


def test_2017_rule_excludes_secondhand_for_individual():
    asset = PlantAsset("Existing oven", 1200, 12, is_new=False)
    assert not asset.eligible(
        investor_is_individual=True,
        property_is_second_hand=True,
        acquired_after_9may2017=True,
    )
    # ...but a new asset the investor installed is fine.
    new_asset = PlantAsset("New oven", 1200, 12, is_new=True)
    assert new_asset.eligible(
        investor_is_individual=True,
        property_is_second_hand=True,
        acquired_after_9may2017=True,
    )


def test_2017_rule_does_not_apply_to_company():
    asset = PlantAsset("Existing oven", 1200, 12, is_new=False)
    assert asset.eligible(
        investor_is_individual=False,
        property_is_second_hand=True,
        acquired_after_9may2017=True,
    )


# ---------------------------------------------------------------------------
# Combined projection
# ---------------------------------------------------------------------------

def test_projection_excludes_ineligible_plant():
    inputs = ProjectionInputs(
        capital_works=[CapitalWorksItem("Reno", 2008, 30_000)],
        plant=[
            PlantAsset("New carpet", 8000, 8, method="PC", start_year=2024, is_new=True),
            PlantAsset("Old oven", 1200, 12, start_year=2024, is_new=False),
        ],
        owner_start_year=2024,
        horizon_years=40,
        marginal_tax_rate=0.37,
    )
    result = build_projection(inputs)
    assert len(result.excluded_plant) == 1
    assert result.excluded_plant[0].description == "Old oven"
    assert len(result.rows) == 40
    # Year 1: 750 (Div43) + 1000 (carpet PC) = 1750.
    assert math.isclose(result.rows[0].total, 1750.0)
    assert math.isclose(result.estimated_tax_saving_total, result.grand_total * 0.37)


# ---------------------------------------------------------------------------
# Validation — cross-referencing proposed data against the law
# ---------------------------------------------------------------------------

def test_validation_flags_claimed_deduction_on_pre1985_build():
    item = CapitalWorksItem("Original building", 1930, 200_000)
    report = validate_capital_works(item, claimed_deductible=True)
    assert not report.ok  # has a blocking error
    assert any(i.field == "deductible" for i in report.errors)


def test_validation_flags_wrong_rate():
    item = CapitalWorksItem("Reno", 2008, 30_000)
    report = validate_capital_works(item, claimed_rate=0.04)  # should be 0.025
    assert any(i.field == "rate" and i.suggested_value == 0.025 for i in report.errors)


def test_validation_flags_effective_life_deviation():
    # Carpet reference is 8 years; propose 25 -> warning with suggested value.
    asset = PlantAsset("Carpet", 8000, effective_life=25, method="DV", start_year=2024, is_new=True)
    report = validate_plant_asset(asset, basis="post_2026")
    warnings = [i for i in report.warnings if i.field == "effective_life"]
    assert warnings and warnings[0].suggested_value == 8


def test_validation_flags_claimed_secondhand_deduction():
    asset = PlantAsset("Existing oven", 1200, 12, is_new=False)
    report = validate_plant_asset(
        asset,
        investor_is_individual=True,
        property_is_second_hand=True,
        acquired_after_9may2017=True,
        claimed_deductible=True,
    )
    assert not report.ok
    assert any(i.field == "deductible" for i in report.errors)

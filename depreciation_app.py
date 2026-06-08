"""Australian investment-property depreciation estimator (Streamlit).

A freemium tax-depreciation tool:

  * Free estimator  — public-facing: one property, a couple of capital-works
                      items and assets, headline numbers and a 40-year chart.
  * Pro (surveyor)  — unlimited dated improvement line items, full plant &
                      equipment register, CSV export, optional LLM-assisted
                      extraction from free text.

The depreciation maths lives in the reusable `depreciation` package (engine +
validation), so the same logic can later back a SaaS API for quantity surveyors.

Every LLM-generated value is cross-referenced against the tax rules by the
`depreciation.validation` layer before it is used — the statutory engine is the
source of truth, the model only proposes.

NOTE: estimator only. Real claims require a quantity surveyor's schedule. Not tax
advice.

Run with:  streamlit run depreciation_app.py
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd
import streamlit as st

from depreciation import assets as asset_ref
from depreciation import llm
from depreciation.costbase import PurchaseDetails, compute_cost_base
from depreciation.gearing import GearingInputs, is_grandfathered, project_gearing
from depreciation.calc import (
    CapitalWorksItem,
    PlantAsset,
    ProjectionInputs,
    build_projection,
    div43_rate_and_life,
)
from depreciation.validation import validate_all

CURRENT_YEAR = _dt.date.today().year

st.set_page_config(page_title="AU Property Depreciation", page_icon=":house:")

# Free-tier caps (the freemium boundary). Pro removes them.
FREE_MAX_IMPROVEMENTS = 2
FREE_MAX_ASSETS = 3


# ---------------------------------------------------------------------------
# Sidebar — plan, white-label, and global property settings
# ---------------------------------------------------------------------------

st.sidebar.title(":house: Depreciation")

plan = st.sidebar.radio(
    "Plan",
    ["Free estimator", "Pro (surveyor)"],
    help=(
        "Free is the public estimator. Pro unlocks unlimited improvement line "
        "items, the full asset register, CSV export, and LLM-assisted extraction. "
        "(Auth/billing would gate this in production.)"
    ),
)
is_pro = plan.startswith("Pro")

if is_pro:
    firm = st.sidebar.text_input("Firm name (white-label)", value="")
    if firm:
        st.sidebar.caption(f"Prepared by **{firm}**")

st.sidebar.divider()
st.sidebar.subheader("Property & investor")

investor_type = st.sidebar.selectbox(
    "Investor type", ["Individual", "Company / trust (excluded entity)"]
)
investor_is_individual = investor_type == "Individual"

second_hand = st.sidebar.checkbox(
    "Second-hand when purchased", value=True,
    help="Affects the 2017 restriction on existing plant & equipment.",
)
purchase_year = st.sidebar.number_input(
    "Year purchased", min_value=1950, max_value=CURRENT_YEAR + 1, value=2024
)
acquired_after_9may2017 = purchase_year > 2017 or (
    purchase_year == 2017  # boundary: 9 May 2017; treat 2017 purchases as after
)
income_start_year = st.sidebar.number_input(
    "First year rented (income-producing)",
    min_value=1950, max_value=CURRENT_YEAR + 1, value=int(purchase_year),
)

basis_label = st.sidebar.selectbox(
    "Effective-life basis (Division 40)",
    ["Post-2026 (LI 2025/20)", "Pre-2026 (TR 2022/1)"],
    help="Which ATO effective-life determination to apply to plant & equipment.",
)
basis = "post_2026" if basis_label.startswith("Post") else "pre_2026"

marginal_rate = st.sidebar.slider(
    "Marginal tax rate (for estimated saving)", 0.0, 0.47, 0.37, 0.01,
    format="%.2f",
)

st.sidebar.caption(
    "Estimator only — not tax advice. Real claims need a quantity surveyor's "
    "schedule."
)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title(":house: AU Investment Property Depreciation")
st.write(
    "Estimate **Division 43** (capital works) and **Division 40** (plant & "
    "equipment) deductions over 40 years. Older buildings often still claim via "
    "post-1987 *renovations* even when the original structure does not."
)


def _render_validation(report) -> None:
    """Render a ValidationReport as Streamlit error/warning/info banners."""
    if not report.issues:
        st.success("No issues — proposal is consistent with the tax rules.")
        return
    for issue in report.issues:
        msg = str(issue)
        if issue.severity == "error":
            st.error(msg)
        elif issue.severity == "warning":
            st.warning(msg)
        else:
            st.info(msg)


# ---------------------------------------------------------------------------
# Section 1 — Capital works (Division 43)
# ---------------------------------------------------------------------------

st.header("1 · Capital works (Division 43)", divider="gray")

col_a, col_b = st.columns(2)
with col_a:
    build_year = st.number_input(
        "Original build year", min_value=1850, max_value=CURRENT_YEAR,
        value=1930,
    )
with col_b:
    original_cost = st.number_input(
        "Original construction cost ($)", min_value=0, value=0, step=1000,
        help="Leave 0 if unknown / pre-1985 (a surveyor estimates this).",
    )

# Show the statutory position for the original structure up-front.
orig_rate, orig_life = div43_rate_and_life(int(build_year))
if orig_rate == 0:
    st.info(
        f"Original {int(build_year)} structure: **not eligible** for Division 43 "
        "(residential construction before 18 Jul 1985). Only post-1987 "
        "improvements below can be claimed."
    )
else:
    st.success(
        f"Original {int(build_year)} structure: **{orig_rate:.1%}** per year over "
        f"{orig_life} years."
    )

st.markdown("**Improvements / works** — choose the tax treatment of each:")

# Friendly labels <-> engine `kind` values.
KIND_LABELS = {
    "Capital works (2.5%/yr)": "capital_works",
    "Repair (100% this year)": "repair",
    "Initial repair (capital)": "initial_repair",
}
LABEL_FOR_KIND = {v: k for k, v in KIND_LABELS.items()}

st.caption(
    "**Capital works** = structural improvement, 2.5%/yr over 40 years. "
    "**Repair** = restores original condition, 100% deductible the year you do it. "
    "**Initial repair** = fixing a defect that existed when you bought "
    "(e.g. restumping a house that was already failing) — capital, *not* an "
    "immediate deduction; modelled as Division 43 if structural."
)

improvements_seed = pd.DataFrame(
    [
        {"description": "Kitchen renovation", "completion_year": 2008, "cost": 25000,
         "treatment": "Capital works (2.5%/yr)"},
        {"description": "New front fence", "completion_year": 2024, "cost": 6000,
         "treatment": "Capital works (2.5%/yr)"},
        {"description": "Restumping (pre-existing rot)", "completion_year": 2024, "cost": 30000,
         "treatment": "Initial repair (capital)"},
        {"description": "Replace broken window", "completion_year": 2025, "cost": 800,
         "treatment": "Repair (100% this year)"},
    ]
)
improvements_df = st.data_editor(
    improvements_seed,
    num_rows="dynamic",
    use_container_width=True,
    key="improvements",
    column_config={
        "description": st.column_config.TextColumn("Description"),
        "completion_year": st.column_config.NumberColumn(
            "Year completed", min_value=1900, max_value=CURRENT_YEAR, step=1
        ),
        "cost": st.column_config.NumberColumn("Cost ($)", min_value=0, step=1000),
        "treatment": st.column_config.SelectboxColumn(
            "Treatment", options=list(KIND_LABELS), required=True
        ),
    },
)

if not is_pro and len(improvements_df) > FREE_MAX_IMPROVEMENTS:
    st.warning(
        f"Free plan models the first {FREE_MAX_IMPROVEMENTS} improvements. "
        "Upgrade to Pro for unlimited dated line items."
    )
    improvements_df = improvements_df.head(FREE_MAX_IMPROVEMENTS)


# ---------------------------------------------------------------------------
# Section 2 — Plant & equipment (Division 40)
# ---------------------------------------------------------------------------

st.header("2 · Plant & equipment (Division 40)", divider="gray")

if second_hand and investor_is_individual and acquired_after_9may2017:
    st.info(
        "2017 rule applies: as an individual buying a second-hand property after "
        "9 May 2017, only assets marked **new (installed by you)** are claimable."
    )

assets_seed = pd.DataFrame(
    [
        {"description": "Carpet (new)", "cost": 6000, "is_new": True},
        {"description": "Split-system air conditioner", "cost": 2500, "is_new": True},
        {"description": "Existing oven", "cost": 1200, "is_new": False},
    ]
)
assets_df = st.data_editor(
    assets_seed,
    num_rows="dynamic",
    use_container_width=True,
    key="assets",
    column_config={
        "description": st.column_config.TextColumn("Asset"),
        "cost": st.column_config.NumberColumn("Cost ($)", min_value=0, step=100),
        "is_new": st.column_config.CheckboxColumn("New (installed by you)"),
    },
)

if not is_pro and len(assets_df) > FREE_MAX_ASSETS:
    st.warning(
        f"Free plan models the first {FREE_MAX_ASSETS} assets. Upgrade to Pro for "
        "the full register."
    )
    assets_df = assets_df.head(FREE_MAX_ASSETS)

method_label = st.radio(
    "Division 40 method", ["Diminishing Value (200%)", "Prime Cost"],
    horizontal=True,
)
method = "DV" if method_label.startswith("Diminishing") else "PC"


# ---------------------------------------------------------------------------
# Section 3 — Ongoing expenses while rented
# ---------------------------------------------------------------------------

st.header("3 · Ongoing expenses while rented", divider="gray")
st.write(
    "Log money spent on the property **while it's rented out**. Genuine repairs "
    "and maintenance are 100 % deductible in the year incurred. Replaced assets "
    "(hot-water system, oven, etc.) are Division 40 plant — depreciated from the "
    "year of replacement."
)

MAINT_LABELS = {
    "Repair / maintenance (100% this year)": "repair",
    "Replaced asset — depreciate (Div 40)": "plant",
}

maint_seed = pd.DataFrame(
    [
        {"description": "Plumbing — blocked pipes", "year": CURRENT_YEAR,
         "cost": 1_200, "treatment": "Repair / maintenance (100% this year)"},
        {"description": "Hot water system (new)", "year": CURRENT_YEAR,
         "cost": 2_800, "treatment": "Replaced asset — depreciate (Div 40)"},
    ]
)
maint_df = st.data_editor(
    maint_seed,
    num_rows="dynamic",
    use_container_width=True,
    key="maintenance",
    column_config={
        "description": st.column_config.TextColumn("Description"),
        "year": st.column_config.NumberColumn(
            "Year", min_value=1990, max_value=CURRENT_YEAR + 10, step=1
        ),
        "cost": st.column_config.NumberColumn("Cost ($)", min_value=0, step=100),
        "treatment": st.column_config.SelectboxColumn(
            "Treatment", options=list(MAINT_LABELS), required=True
        ),
    },
)
st.caption(
    "**Repair / maintenance** — restores the property to working condition "
    "(broken pipe, repainting, new tap washer). 100 % deductible the year it's "
    "done, visible in the Repairs line of the projection. "
    "**Replaced asset** — a brand-new depreciable item you install (hot-water "
    "system, oven, air con). Depreciated from the year of replacement; treated "
    "as new so the 2017 second-hand restriction does *not* apply."
)


# ---------------------------------------------------------------------------
# Optional — LLM-assisted extraction (Pro), always validated against the law
# ---------------------------------------------------------------------------

if is_pro:
    with st.expander(":sparkles: Extract from a description (LLM-assisted)"):
        st.caption(
            "Paste an agent listing or site notes. Claude extracts line items; "
            "**every value is then cross-checked against the tax rules** before "
            "anything is used. The model proposes — the statutory engine decides."
        )
        if not llm.is_available():
            st.warning(
                "LLM extraction needs the `anthropic` package and `ANTHROPIC_API_KEY`. "
                "Manual entry above works without it."
            )
        else:
            desc = st.text_area("Property description", height=140, key="llm_desc")
            if st.button("Extract & validate") and desc.strip():
                with st.spinner("Extracting and validating against tax rules…"):
                    result = llm.extract_property_data(
                        desc,
                        basis=basis,
                        investor_is_individual=investor_is_individual,
                        property_is_second_hand=second_hand,
                        acquired_after_9may2017=acquired_after_9may2017,
                        owner_start_year=int(income_start_year),
                    )
                st.markdown("**Proposed capital works**")
                st.dataframe(
                    pd.DataFrame(
                        [(c.description, c.completion_year, c.cost) for c in result.capital_works],
                        columns=["description", "completion_year", "cost"],
                    ),
                    use_container_width=True,
                )
                st.markdown("**Proposed plant & equipment**")
                st.dataframe(
                    pd.DataFrame(
                        [(p.description, p.cost, p.effective_life, p.is_new) for p in result.plant],
                        columns=["asset", "cost", "effective_life", "is_new"],
                    ),
                    use_container_width=True,
                )
                _render_validation(result.validation)
                st.caption(
                    "Copy any rows you want into the tables above — kept manual on "
                    "purpose so a surveyor signs off on the figures."
                )


# ---------------------------------------------------------------------------
# Build engine inputs from the tables
# ---------------------------------------------------------------------------

def _build_capital_works() -> list[CapitalWorksItem]:
    items: list[CapitalWorksItem] = []
    if original_cost > 0:
        items.append(
            CapitalWorksItem("Original building", int(build_year), float(original_cost))
        )
    for _, row in improvements_df.iterrows():
        desc = str(row.get("description") or "").strip()
        year = row.get("completion_year")
        cost = row.get("cost")
        if not desc or pd.isna(year) or pd.isna(cost):
            continue
        kind = KIND_LABELS.get(row.get("treatment"), "capital_works")
        items.append(CapitalWorksItem(desc, int(year), float(cost), kind=kind))
    return items


def _build_plant() -> list[PlantAsset]:
    out: list[PlantAsset] = []
    for _, row in assets_df.iterrows():
        desc = str(row.get("description") or "").strip()
        cost = row.get("cost")
        if not desc or pd.isna(cost):
            continue
        life = asset_ref.effective_life_for(desc, basis) or 10.0
        out.append(
            PlantAsset(
                description=desc,
                cost=float(cost),
                effective_life=life,
                method=method,
                start_year=int(income_start_year),
                is_new=bool(row.get("is_new")),
            )
        )
    return out


def _build_maintenance_repairs() -> list[CapitalWorksItem]:
    """Repair/maintenance rows from Section 3 → immediate deduction items."""
    out: list[CapitalWorksItem] = []
    for _, row in maint_df.iterrows():
        desc = str(row.get("description") or "").strip()
        year = row.get("year")
        cost = row.get("cost")
        treatment = row.get("treatment", "")
        if not desc or pd.isna(year) or pd.isna(cost):
            continue
        if MAINT_LABELS.get(treatment) == "repair":
            out.append(CapitalWorksItem(desc, int(year), float(cost), kind="repair"))
    return out


def _build_replacement_assets() -> list[PlantAsset]:
    """Replaced-asset rows from Section 3 → new Div 40 plant from the replacement year."""
    out: list[PlantAsset] = []
    for _, row in maint_df.iterrows():
        desc = str(row.get("description") or "").strip()
        year = row.get("year")
        cost = row.get("cost")
        treatment = row.get("treatment", "")
        if not desc or pd.isna(year) or pd.isna(cost):
            continue
        if MAINT_LABELS.get(treatment) == "plant":
            life = asset_ref.effective_life_for(desc, basis) or 10.0
            out.append(
                PlantAsset(
                    description=desc,
                    cost=float(cost),
                    effective_life=life,
                    method=method,
                    start_year=int(year),
                    is_new=True,  # always new — not subject to the 2017 restriction
                )
            )
    return out


capital_works = _build_capital_works() + _build_maintenance_repairs()
plant = _build_plant() + _build_replacement_assets()


# ---------------------------------------------------------------------------
# Section 3 — Results
# ---------------------------------------------------------------------------

st.header("4 · Projection", divider="gray")

inputs = ProjectionInputs(
    capital_works=capital_works,
    plant=plant,
    owner_start_year=int(income_start_year),
    horizon_years=40,
    investor_is_individual=investor_is_individual,
    property_is_second_hand=second_hand,
    acquired_after_9may2017=acquired_after_9may2017,
    marginal_tax_rate=marginal_rate,
)
result = build_projection(inputs)

# Validate the manually-entered dataset too (same guardrail as the LLM path).
manual_report = validate_all(
    capital_works,
    plant,
    basis=basis,
    investor_is_individual=investor_is_individual,
    property_is_second_hand=second_hand,
    acquired_after_9may2017=acquired_after_9may2017,
    purchase_year=int(purchase_year),
)
with st.expander("Validation against tax rules", expanded=bool(manual_report.errors)):
    _render_validation(manual_report)

if result.excluded_plant:
    names = ", ".join(a.description for a in result.excluded_plant)
    st.caption(f"Excluded by the 2017 second-hand rule: {names}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Year 1 deduction", f"${result.year_one_total:,.0f}")
m2.metric("Year 1 tax saving", f"${result.year_one_total * marginal_rate:,.0f}")
m3.metric("First 5 years", f"${result.first_n_total(5):,.0f}")
m4.metric("40-year total", f"${result.grand_total:,.0f}")

chart_df = pd.DataFrame(
    {
        "Year": [r.year for r in result.rows],
        "Division 43": [r.div43 for r in result.rows],
        "Division 40": [r.div40 for r in result.rows],
        "Repairs": [r.repairs for r in result.rows],
        "Total": [r.total for r in result.rows],
    }
).set_index("Year")

st.subheader("Deductions over time")
st.line_chart(chart_df)

# Free shows a short table; Pro shows the full 40-year schedule + export.
st.subheader("Yearly schedule")
display_df = chart_df.reset_index()
if is_pro:
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download full schedule (CSV)",
        display_df.to_csv(index=False).encode("utf-8"),
        file_name="depreciation_schedule.csv",
        mime="text/csv",
    )
else:
    st.dataframe(display_df.head(10), use_container_width=True, hide_index=True)
    st.info(
        "Free plan shows the first 10 years. **Upgrade to Pro** for the full "
        "40-year schedule and CSV export."
    )


# ---------------------------------------------------------------------------
# Section 4 — Negative gearing & cash flow
# ---------------------------------------------------------------------------

st.header("5 · Negative gearing & cash flow", divider="gray")
st.write(
    "Depreciation is a **non-cash** deduction, so it can turn a cash-neutral "
    "property into a tax loss. This combines it with your rent and holding costs "
    "to show the after-tax position."
)

st.markdown(
    "**Weekly rent over time** — add a row each time the rent changes (e.g. "
    "switching to a boarding house). Each rate applies from its *From year* "
    "onward."
)
rent_seed = pd.DataFrame(
    [
        {"from_year": 2024, "weekly_rent": 380},
        {"from_year": int(CURRENT_YEAR), "weekly_rent": 900},
    ]
)
rent_df = st.data_editor(
    rent_seed,
    num_rows="dynamic",
    use_container_width=True,
    key="rent_periods",
    column_config={
        "from_year": st.column_config.NumberColumn(
            "From year", min_value=1990, max_value=CURRENT_YEAR + 40, step=1
        ),
        "weekly_rent": st.column_config.NumberColumn("Rent ($/week)", min_value=0, step=10),
    },
)

# Build the stepped annual-rent schedule {from_year: annual_rent}.
annual_rent_by_year: dict[int, float] = {}
for _, row in rent_df.iterrows():
    fy = row.get("from_year")
    wr = row.get("weekly_rent")
    if pd.isna(fy) or pd.isna(wr):
        continue
    annual_rent_by_year[int(fy)] = float(wr) * 52
# Sensible fallback if the table is emptied.
current_annual_rent = (
    annual_rent_by_year[max(k for k in annual_rent_by_year if k <= CURRENT_YEAR)]
    if any(k <= CURRENT_YEAR for k in annual_rent_by_year)
    else (min(annual_rent_by_year.values()) if annual_rent_by_year else 0.0)
)

gcol1, gcol2 = st.columns(2)
with gcol1:
    loan_balance = st.number_input("Loan balance ($)", min_value=0, value=600_000, step=10_000)
    interest_rate = st.slider("Interest rate (%)", 0.0, 12.0, 6.2, 0.1) / 100.0
    mgmt_pct = st.slider("Property management (% of rent)", 0.0, 12.0, 7.0, 0.5) / 100.0
with gcol2:
    council_rates = st.number_input("Council + water rates ($/yr)", min_value=0, value=3_500, step=100)
    insurance = st.number_input("Insurance ($/yr)", min_value=0, value=1_800, step=100)
    other_expenses = st.number_input(
        "Repairs / strata / other ($/yr)", min_value=0, value=2_000, step=100
    )

loan_interest = loan_balance * interest_rate
# Management fee is applied per-year inside the engine (it tracks each year's rent).
other_cash = council_rates + insurance + other_expenses

# Negative-gearing regime: default from purchase year, with overrides for new
# builds and commercial / commercial-residential (e.g. boarding house) premises.
ngc1, ngc2 = st.columns(2)
with ngc1:
    new_build = st.checkbox(
        "Eligible new build (exempt — keeps negative gearing)", value=False
    )
with ngc2:
    commercial = st.checkbox(
        "Commercial residential / boarding house",
        value=False,
        help=(
            "Run as commercial residential premises (e.g. a boarding house). "
            "Commercial property is outside the 2026 residential negative-gearing "
            "measure, so it keeps full negative gearing regardless of purchase "
            "date. (Income-tax gearing only — GST / commercial-residential rules "
            "are out of scope here.)"
        ),
    )

default_grandfathered = is_grandfathered(int(purchase_year), new_build)
if commercial:
    st.success(
        "Commercial residential / boarding house: **exempt** from the 2026 "
        "residential negative-gearing changes — full offset against other income "
        "applies regardless of purchase date."
    )
    grandfathered = True
else:
    regime = st.radio(
        "Negative gearing treatment",
        [
            "Grandfathered — full offset against other income",
            "Restricted — losses quarantined (carried forward)",
        ],
        index=0 if default_grandfathered else 1,
        help=(
            "2026 Budget: negative gearing on established residential property is "
            "abolished from 1 Jul 2027 for properties bought after 12 May 2026. "
            "Earlier purchases (and eligible new builds) are grandfathered and keep "
            "full negative gearing. Default is set from your purchase year above."
        ),
    )
    grandfathered = regime.startswith("Grandfathered")
    if int(purchase_year) <= 2026 and not new_build:
        st.caption(
            f"Your {int(purchase_year)} purchase is **grandfathered** — it keeps "
            "full negative gearing under current rules (until you sell)."
        )

g_inputs = GearingInputs(
    annual_rent=current_annual_rent,
    loan_interest=loan_interest,
    other_cash_expenses=other_cash,
    marginal_tax_rate=marginal_rate,
    grandfathered=grandfathered,
    commercial=commercial,
    mgmt_pct=mgmt_pct,
    annual_rent_by_year=annual_rent_by_year or None,
)
depr_by_year = {r.year: r.total for r in result.rows}
g_result = project_gearing(g_inputs, depr_by_year)
gy = g_result.year_one

if gy is not None:
    st.subheader("Year 1 position")
    gm1, gm2, gm3, gm4 = st.columns(4)
    gm1.metric(
        "Taxable result",
        f"${gy.taxable_result:,.0f}",
        help="Rent − cash costs − depreciation. Negative = a tax loss.",
    )
    gm2.metric(
        "Tax effect",
        f"${gy.tax_effect:,.0f}",
        help="Positive = tax saved this year; under the restricted regime a loss "
        "is carried forward instead.",
    )
    gm3.metric("Pre-tax cash flow", f"${gy.pretax_cashflow:,.0f}")
    gm4.metric(
        "After-tax cost", f"${gy.aftertax_weekly:,.0f}/wk",
        help="After-tax holding cost per week (negative = out of pocket).",
    )

    if not grandfathered:
        st.warning(
            f"Restricted regime: the loss does not reduce your salary tax. "
            f"${gy.carried_forward_loss:,.0f} is carried forward to offset future "
            "rental income or a capital gain on sale."
        )

    g_chart = pd.DataFrame(
        {
            "Year": [r.year for r in g_result.rows],
            "Annual rent": [r.rent for r in g_result.rows],
            "Pre-tax cash flow": [r.pretax_cashflow for r in g_result.rows],
            "After-tax cash flow": [r.aftertax_cashflow for r in g_result.rows],
        }
    ).set_index("Year")
    st.subheader("Cash flow over time")
    st.caption(
        "As depreciation declines over the years, the tax benefit shrinks and "
        "the after-tax cost typically rises."
    )
    st.line_chart(g_chart)

    if is_pro:
        g_full = pd.DataFrame(
            {
                "Year": [r.year for r in g_result.rows],
                "Rent": [round(r.rent) for r in g_result.rows],
                "Cash expenses": [round(r.cash_expenses) for r in g_result.rows],
                "Depreciation": [round(r.depreciation) for r in g_result.rows],
                "Taxable result": [round(r.taxable_result) for r in g_result.rows],
                "Tax effect": [round(r.tax_effect) for r in g_result.rows],
                "Carried-fwd loss": [round(r.carried_forward_loss) for r in g_result.rows],
                "After-tax cash flow": [round(r.aftertax_cashflow) for r in g_result.rows],
            }
        )
        with st.expander("Full cash-flow schedule"):
            st.dataframe(g_full, use_container_width=True, hide_index=True)
            st.download_button(
                "Download cash-flow schedule (CSV)",
                g_full.to_csv(index=False).encode("utf-8"),
                file_name="gearing_schedule.csv",
                mime="text/csv",
            )

st.caption(
    "Negative gearing rules per the 2026 Budget measure. Estimator only — not tax "
    "advice. Confirm grandfathering and any sale/CGT treatment with your accountant."
)


# ---------------------------------------------------------------------------
# Section 5 — Purchase price, land/building split & CGT cost base
# ---------------------------------------------------------------------------

st.header("6 · Purchase price, land/building split & CGT", divider="gray")
st.write(
    "Land is never depreciable. The **building value** (purchase price minus land) "
    "gives an order-of-magnitude check on your Division 43 depreciable base. The "
    "**cost base** accumulates over ownership and reduces your taxable gain when "
    "you eventually sell. Use a quantity surveyor for actual construction cost."
)

pc1, pc2 = st.columns(2)
with pc1:
    purchase_price = st.number_input(
        "Purchase price ($)", min_value=0, value=700_000, step=5_000
    )
    land_value = st.number_input(
        "Land value ($)",
        min_value=0, value=280_000, step=5_000,
        help="From council valuation, ATO estimate, or your quantity surveyor's report.",
    )
with pc2:
    stamp_duty = st.number_input(
        "Stamp duty ($)", min_value=0, value=28_000, step=500
    )
    legal_fees = st.number_input(
        "Legal / conveyancing fees ($)", min_value=0, value=2_000, step=100
    )
    other_acquisition = st.number_input(
        "Other acquisition costs ($)", min_value=0, value=0, step=100,
        help="Building inspection, buyer's agent, etc.",
    )

purchase = PurchaseDetails(
    purchase_price=float(purchase_price),
    land_value=float(land_value),
    stamp_duty=float(stamp_duty),
    legal_fees=float(legal_fees),
    other_acquisition_costs=float(other_acquisition),
)

# Land / building split metrics.
sp1, sp2, sp3, sp4 = st.columns(4)
sp1.metric("Land value", f"${purchase.land_value:,.0f}",
           f"{purchase.land_pct:.0%} of purchase")
sp2.metric("Building value", f"${purchase.building_value:,.0f}",
           f"{purchase.building_pct:.0%} of purchase")
sp3.metric("Div 43 base (indicative)", f"${purchase.building_value:,.0f}",
           help="Building value as a proxy — actual construction cost from a QS.")
sp4.metric("Acquisition cost base", f"${purchase.element1_and_2:,.0f}")

if purchase.building_value > 0 and result.total_div43 == 0:
    st.info(
        f"No Division 43 deductions are claimed on your improvements. "
        f"If post-1987 capital works exist, you could claim 2.5% on ~"
        f"${purchase.building_value:,.0f} of building value."
    )

st.divider()

# CGT cost base tracker — accumulates over the projection.
st.subheader("CGT cost base over time")
st.caption(
    "Division 43 deductions reduce your cost base year by year. "
    "Initial repairs are added as capital. The adjusted cost base determines "
    "your taxable gain on sale."
)

cb = compute_cost_base(
    purchase,
    capital_works_items=capital_works,
    div43_deductions_taken=result.total_div43,
)

cb1, cb2, cb3 = st.columns(3)
cb1.metric("Purchase + acq. costs", f"${purchase.element1_and_2:,.0f}")
cb2.metric("+ Initial repairs (capital)", f"${cb.capital_additions:,.0f}")
cb3.metric(
    "− Div 43 deductions (40-yr)",
    f"${result.total_div43:,.0f}",
    help="Div 43 claimed reduces cost base under s 110-45 ITAA 1997.",
)
st.metric(
    "Adjusted cost base (after 40 yrs)",
    f"${cb.adjusted_cost_base:,.0f}",
    help="Estimated cost base after full 40-yr depreciation claim.",
)

# Year-by-year cost base chart.
cumulative_div43 = 0.0
cb_rows = []
for r in result.rows:
    cumulative_div43 += r.div43
    cb_rows.append({
        "Year": r.year,
        "Cost base": (
            purchase.element1_and_2
            + cb.capital_additions
            - cumulative_div43
        ),
    })
cb_chart = pd.DataFrame(cb_rows).set_index("Year")
st.line_chart(cb_chart)

st.divider()

# CGT on sale estimator.
st.subheader("Estimated CGT on sale")
st.caption(
    "Estimates the capital gains tax if you sold at a chosen price at a chosen year, "
    "using the cost base adjusted to that year's Div 43 deductions taken so far. "
    "Not a substitute for advice — CGT involves many factors not modelled here."
)

sale_col1, sale_col2 = st.columns(2)
with sale_col1:
    sale_price = st.number_input(
        "Estimated sale price ($)", min_value=0, value=int(purchase_price * 1.5), step=5_000
    )
    sale_year = st.number_input(
        "Year of sale", min_value=int(income_start_year),
        max_value=int(income_start_year) + 40,
        value=min(int(income_start_year) + 10, int(income_start_year) + 40),
    )
with sale_col2:
    held_over_12m = st.checkbox("Held > 12 months (50% CGT discount)", value=True)

# Find cumulative Div 43 up to the sale year.
div43_to_sale = sum(r.div43 for r in result.rows if r.year <= int(sale_year))
cb_at_sale = compute_cost_base(
    purchase,
    capital_works_items=capital_works,
    div43_deductions_taken=div43_to_sale,
)
gain = cb_at_sale.estimated_gain(float(sale_price))
cgt = cb_at_sale.cgt_payable(
    float(sale_price),
    marginal_rate,
    held_over_12_months=held_over_12m,
    is_individual=investor_is_individual,
)

cgt1, cgt2, cgt3, cgt4 = st.columns(4)
cgt1.metric("Sale price", f"${sale_price:,.0f}")
cgt2.metric(f"Cost base at {int(sale_year)}", f"${cb_at_sale.adjusted_cost_base:,.0f}")
cgt3.metric(
    "Gross capital gain" if gain >= 0 else "Capital loss",
    f"${gain:,.0f}",
)
discount_note = " (50% discount applied)" if held_over_12m and investor_is_individual and gain > 0 else ""
cgt4.metric(
    f"Estimated CGT{discount_note}",
    f"${cgt:,.0f}",
    help=f"At {marginal_rate:.0%} marginal rate.",
)

if gain < 0:
    st.info(
        f"At ${sale_price:,.0f} you'd make a **capital loss** of ${-gain:,.0f} — "
        "this can offset capital gains on other assets."
    )
elif held_over_12m and investor_is_individual:
    discounted_gain = gain * 0.5
    st.caption(
        f"Gross gain ${gain:,.0f} × 50% discount = ${discounted_gain:,.0f} taxable "
        f"× {marginal_rate:.0%} = ${cgt:,.0f} CGT. "
        f"Net proceeds after CGT ≈ ${sale_price - cgt:,.0f}."
    )

if is_pro:
    cgt_df = pd.DataFrame(
        [
            {
                "Year of sale": r.year,
                "Div 43 claimed to date": round(
                    sum(rr.div43 for rr in result.rows if rr.year <= r.year)
                ),
                "Adjusted cost base": round(
                    purchase.element1_and_2
                    + cb.capital_additions
                    - sum(rr.div43 for rr in result.rows if rr.year <= r.year)
                ),
            }
            for r in result.rows
        ]
    )
    with st.expander("Cost base by year (Pro)"):
        st.dataframe(cgt_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download cost base table (CSV)",
            cgt_df.to_csv(index=False).encode("utf-8"),
            file_name="cost_base.csv",
            mime="text/csv",
        )

st.caption(
    "Estimator only — not tax advice. CGT cost base calculation simplified: "
    "excludes apportionment for private use, depreciation recapture adjustments, "
    "and other factors. Confirm with your accountant before any sale decision."
)

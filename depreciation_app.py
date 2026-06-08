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

st.markdown("**Improvements / renovations** (each runs its own 40-yr clock from completion):")

improvements_seed = pd.DataFrame(
    [
        {"description": "Kitchen renovation", "completion_year": 2008, "cost": 25000},
        {"description": "Bathroom + extension", "completion_year": 2015, "cost": 40000},
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
        items.append(CapitalWorksItem(desc, int(year), float(cost)))
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


capital_works = _build_capital_works()
plant = _build_plant()


# ---------------------------------------------------------------------------
# Section 3 — Results
# ---------------------------------------------------------------------------

st.header("3 · Projection", divider="gray")

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

st.header("4 · Negative gearing & cash flow", divider="gray")
st.write(
    "Depreciation is a **non-cash** deduction, so it can turn a cash-neutral "
    "property into a tax loss. This combines it with your rent and holding costs "
    "to show the after-tax position."
)

gcol1, gcol2 = st.columns(2)
with gcol1:
    weekly_rent = st.number_input("Rent ($/week)", min_value=0, value=550, step=10)
    loan_balance = st.number_input("Loan balance ($)", min_value=0, value=600_000, step=10_000)
    interest_rate = st.slider("Interest rate (%)", 0.0, 12.0, 6.2, 0.1) / 100.0
with gcol2:
    council_rates = st.number_input("Council + water rates ($/yr)", min_value=0, value=3_500, step=100)
    insurance = st.number_input("Insurance ($/yr)", min_value=0, value=1_800, step=100)
    mgmt_pct = st.slider("Property management (% of rent)", 0.0, 12.0, 7.0, 0.5) / 100.0
    other_expenses = st.number_input(
        "Repairs / strata / other ($/yr)", min_value=0, value=2_000, step=100
    )

annual_rent = weekly_rent * 52
loan_interest = loan_balance * interest_rate
mgmt_fee = annual_rent * mgmt_pct
other_cash = council_rates + insurance + mgmt_fee + other_expenses

# Negative-gearing regime: default from purchase year, with an override and a
# new-build exemption.
new_build = st.checkbox(
    "Eligible new build (exempt — keeps negative gearing)", value=False
)
default_grandfathered = is_grandfathered(int(purchase_year), new_build)
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
        f"Your {int(purchase_year)} purchase is **grandfathered** — it keeps full "
        "negative gearing under current rules (until you sell)."
    )

g_inputs = GearingInputs(
    annual_rent=annual_rent,
    loan_interest=loan_interest,
    other_cash_expenses=other_cash,
    marginal_tax_rate=marginal_rate,
    grandfathered=grandfathered,
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

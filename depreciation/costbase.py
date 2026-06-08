"""Purchase price, land/building split, CGT cost base, and estimated sale gain.

Tracks the two components that matter at acquisition and at disposal:

1. Land / building split
   Land is never depreciable. The building value (purchase price minus land)
   is a useful proxy for the Division 43 depreciable base when the original
   construction cost is unknown, but it is NOT the same as construction cost
   — a quantity surveyor determines the true construction cost. Use the derived
   building value as an order-of-magnitude check only.

2. CGT cost base (s 110-25 ITAA 1997)
   The cost base accumulates over ownership and reduces the taxable gain on sale:
     Element 1 -- purchase price (plus incidentals rolled in here for simplicity)
     Element 2 -- acquisition costs: stamp duty, legal/conveyancing fees
     Element 3 -- costs of ownership (interest normally NOT included; council
                  rates when not deducted -- typically negligible here)
     Element 4 -- capital expenditure that did not produce assessable income
                  and is not already deducted. Includes initial repairs and
                  non-structural improvements NOT deducted elsewhere.
     Element 5 -- capital expenditure to establish, preserve or defend title

   Items claimed as a Division 43 deduction are NOT added to the cost base for
   their full amount; instead the cost base is reduced by the Division 43
   deductions taken (the "cost base adjustments" in s 110-45). This model keeps
   it simple: Div 43 deductions reduce the cost base $ for $; Div 40 assets are
   not part of the building cost base.

3. Estimated capital gain / loss on sale
   Taxable gain = sale proceeds - adjusted cost base (after Div 43 reductions).
   For individuals holding > 12 months: 50% CGT discount applies.
   CGT payable = discounted gain * marginal tax rate.

This is a simplification. Real CGT involves cost-base apportionment, depreciation
recapture adjustments, and other factors. Not tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PurchaseDetails:
    purchase_price: float
    land_value: float           # ATO estimate or council valuation
    stamp_duty: float = 0.0
    legal_fees: float = 0.0
    other_acquisition_costs: float = 0.0

    @property
    def building_value(self) -> float:
        """Indicative building value (not construction cost)."""
        return max(0.0, self.purchase_price - self.land_value)

    @property
    def land_pct(self) -> float:
        if self.purchase_price <= 0:
            return 0.0
        return self.land_value / self.purchase_price

    @property
    def building_pct(self) -> float:
        return 1.0 - self.land_pct

    @property
    def element1_and_2(self) -> float:
        """Cost base elements 1+2: purchase price + acquisition costs."""
        return (
            self.purchase_price
            + self.stamp_duty
            + self.legal_fees
            + self.other_acquisition_costs
        )


@dataclass
class CostBaseResult:
    """Running cost base and sale gain estimate."""

    purchase_details: PurchaseDetails
    # Structural capital improvements added to the cost base (Element 4):
    # initial repairs + non-deducted capital works.
    capital_additions: float = 0.0
    # Total Div 43 deductions taken: reduces the cost base under s 110-45.
    total_div43_claimed: float = 0.0

    @property
    def adjusted_cost_base(self) -> float:
        return (
            self.purchase_details.element1_and_2
            + self.capital_additions
            - self.total_div43_claimed
        )

    def estimated_gain(self, sale_price: float) -> float:
        return sale_price - self.adjusted_cost_base

    def cgt_payable(
        self,
        sale_price: float,
        marginal_rate: float,
        held_over_12_months: bool = True,
        is_individual: bool = True,
    ) -> float:
        gain = self.estimated_gain(sale_price)
        if gain <= 0:
            return 0.0
        if is_individual and held_over_12_months:
            gain = gain * 0.5  # 50% CGT discount
        return gain * marginal_rate


def compute_cost_base(
    purchase: PurchaseDetails,
    *,
    capital_works_items: list,     # CapitalWorksItem list from calc
    div43_deductions_taken: float,
) -> CostBaseResult:
    """Build the CGT cost base from purchase details and capital works history.

    Items of kind 'initial_repair' are added to the cost base (capital,
    not deducted). Division 43 deductions taken reduce it under s 110-45.
    """
    from depreciation.calc import CapitalWorksItem

    # Initial repairs: capital expenditure not immediately deducted (Element 4).
    initial_repair_total = sum(
        item.cost
        for item in capital_works_items
        if getattr(item, "kind", "capital_works") == "initial_repair"
    )

    return CostBaseResult(
        purchase_details=purchase,
        capital_additions=initial_repair_total,
        total_div43_claimed=div43_deductions_taken,
    )

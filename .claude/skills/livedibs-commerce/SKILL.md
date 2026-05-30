---
name: livedibs-commerce
description: "Build and reason about LiveDibs — a platform-agnostic comment-claim live-commerce layer for Facebook/Instagram (and TikTok Shop when local) that adds the hold + invoice + Stripe checkout layer Meta removed. Use when implementing or designing any LiveDibs feature: market localisation for Australia (GST), UK (VAT), and US (sales tax); tax-inclusive vs tax-exclusive price display; per-product tax classes and invoice rounding; consumer-law copy (AU Consumer Guarantees, UK 14-day cooling-off, US no-general-cooling-off/FTC); buyer-locality gating (local-only default, cross-border opt-in) and order-market resolution; Stripe Connect Express payment routing and FX; platform availability gating (market_platforms); the always-on overstock storefront (auto-relist, Buy It Now, time-boxed Sale events, Best Offer); and i18n formatting (Intl, seller timezones, claim keywords). Apply whenever building the markets/sellers/products schema, checkout, claim engine, invoices, or localisation/legal strings for LiveDibs."
---

# LiveDibs Commerce

Design and implementation rules for **LiveDibs**, a one-codebase live-commerce platform where the market is resolved at runtime. Nothing about currency, tax, consumer-law text, payment rails, platform availability, or buyer locality is hardcoded.

## When to use this skill

Apply when the task touches any of:
- The `markets`, `sellers`, `products`, `market_platforms`, `sale_events`, or `offers` schema
- Price display, tax calculation/rounding, or invoices (AU GST / UK VAT / US Stripe Tax)
- Consumer-law / legal copy injected into DMs, invoices, or checkout
- The claim engine ("SOLD"/"DIBS" → hold → invoice → Stripe checkout)
- Buyer-locality gating, shipping-country restriction, or cross-border mode
- Stripe Connect payment routing, payouts, or FX
- The overstock storefront: Buy It Now, Sale events, Best Offer
- i18n: `Intl.NumberFormat` / `Intl.DateTimeFormat`, seller timezones, claim keywords

## Core principles (apply by default)

1. **Market is config, resolved at runtime** from the seller's `market_code` (or, in cross-border mode, the buyer's ship-to). Never hardcode currency, tax, or legal text.
2. **Local buyers by default.** `sellers.ships_internationally = false` ⇒ ship-to is restricted to the seller's own market, enforced at Stripe Checkout via `allowed_countries`. Cross-border is an explicit opt-in that flips tax/legal/currency resolution to the **destination** market.
3. **Tax display is a legal requirement, not a preference.** AU/UK prices are **tax-inclusive** (store gross `price_cents`; tax component = `gross * rate/(1+rate)`, round half-up per line); US prices are **tax-exclusive** with **Stripe Tax** added at checkout by ship-to. Use per-product `tax_class` — never assume one flat market rate.
4. **Consumer-law copy is per-market and lawyer-gated.** AU = Consumer Guarantees (no general cooling-off); UK = 14-day cooling-off + pre-contract info (mind the exemptions); US = no general internet cooling-off (FTC), seller-posted return policy. Render it on the live flow **and** every overstock listing/checkout (distance selling).
5. **The claim engine is market-neutral.** Only presentation, tax, payment routing, legal copy, locality gating, and overstock behaviour localise.
6. **Overstock reuses the live pipeline.** Buy It Now / Sale events / Best Offer all route through the same hold → invoice → Stripe checkout, inheriting tax, legal, locality, and payment logic. **Auctions are out of scope** (UK online auctions are not exempt from cooling-off).
7. **MilvoTech hard rules:** Stripe-hosted checkout only; never store card data; never enter payment on a shopper's behalf.
8. **Formatting:** always `Intl.NumberFormat(locale, {currency})` for prices and `Intl.DateTimeFormat(locale, {timeZone: seller.timezone})` for dates — timezone is **seller-level**, not market-level.

## Full specification

The complete, authoritative spec — schema, per-market matrix, resolution rules, flows, and the consolidated acceptance tests — is in:

- **`reference/spec-v2.0.md`**

Read it before implementing any LiveDibs feature, and treat its §10 acceptance tests as the definition of done. The §4 legal strings are drafting guidance and require per-jurisdiction lawyer sign-off before any live sale.

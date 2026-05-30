# LiveDibs — Localisation & Commerce Spec v2.0 (Consolidated)

**Supersedes:** Localisation Spec v1 + v1.1 (buyer-locality) + v1.2 (overstock storefront).
**Target implementer:** Claude Opus (Replit Cowork)
**Scope:** Market-specific config for 🇦🇺 Australia · 🇬🇧 United Kingdom · 🇺🇸 United States (extensible to 🇨🇦 🇳🇿 🇸🇬).
**Principle:** One codebase. Market resolved at runtime from a `markets` table + the seller's registered jurisdiction. Currency, tax, consumer-law text, payment rails, platform availability, and buyer locality are config, never hardcoded.
**Legal status:** §4 consumer-law strings are drafting guidance and require per-jurisdiction lawyer sign-off before any live sale.

---

## 0. Why this matters (the strategic read)

- **TikTok Shop is not fully live in Australia yet.** It is launched in the US, UK, and parts of the EU/SEA; AU is early rollout — roughly 20 Australian brands already use TikTok Shop's cross-border capability to sell into the US/UK. That is LiveDibs' opening: an Australian-built, platform-agnostic comment-claim layer that works on Facebook/Instagram **today** in AU, and bolts onto TikTok Shop the moment it lands locally.
- **Meta killed native FB Live Shopping checkout** everywhere — so in every market the "hold + invoice + checkout link" layer is the gap LiveDibs fills.
- **Consumer law differs sharply:** AU has no general online cooling-off but strong non-waivable **Consumer Guarantees**; the UK gives a **14-day no-reason cancellation**; the US has **no general distance-selling cooling-off** (the FTC rule excludes internet-only sales). Wrong on-screen/invoice wording is a compliance risk, especially on impulse live purchases.

---

## 1. Market resolution architecture

```sql
create table markets (
  code              text primary key,        -- 'AU','UK','US'
  display_name      text not null,
  currency          text not null,           -- ISO 4217: AUD, GBP, USD
  locale            text not null,           -- en-AU, en-GB, en-US
  tax_model         text not null,           -- 'gst_inclusive','vat_inclusive','sales_tax_exclusive'
  tax_label         text not null,           -- 'GST','VAT','Sales Tax'
  standard_tax_rate numeric,                 -- 0.10, 0.20, null (=destination calc)
  price_display     text not null,           -- 'tax_inclusive' | 'tax_exclusive'
  cancellation_model text not null,          -- 'consumer_guarantees','cooling_off_14d','no_general_coolingoff'
  timezone_default  text not null,           -- fallback only; sellers carry their own TZ (see §9)
  date_format       text not null,
  enabled           boolean default true
);
```

> **Changes from v1:** dropped `currency_symbol` (redundant — `Intl.NumberFormat` derives the symbol from the currency code and renders `A$`/`US$`/`£` correctly; a stored symbol only invites drift). Renamed `tax_rate_default` → `standard_tax_rate` to signal it is the *standard* rate only; per-product tax classes override it (§3).

```sql
-- seller declares jurisdiction; drives presentation, tax, payment routing, legal copy
alter table sellers
  add column market_code            text references markets(code) default 'AU',
  add column abn_or_tax_id          text,            -- ABN (AU) / VAT no (UK) / EIN (US); validate per market_code
  add column registered_business_name text,
  add column timezone               text,            -- seller-level TZ (§9); falls back to markets.timezone_default
  -- buyer-locality controls (§5)
  add column ships_internationally  boolean not null default false,
  add column allowed_ship_to_markets text[],         -- null/empty ⇒ local only = [market_code]
  -- overstock controls (§8)
  add column auto_list_overstock    boolean not null default false,
  add column accept_best_offers     boolean not null default false;
```

The claim engine is **market-neutral**. Only presentation, tax, payment routing, legal copy, locality gating, and overstock behaviour localise.

---

## 2. Per-market configuration matrix

| Concern | 🇦🇺 Australia | 🇬🇧 United Kingdom | 🇺🇸 United States |
| :--- | :--- | :--- | :--- |
| Currency | AUD ($) | GBP (£) | USD ($) |
| Locale | en-AU | en-GB | en-US |
| Price display | **Tax-inclusive** (GST in price) | **Tax-inclusive** (VAT in price) | **Tax-exclusive** (tax added at checkout) |
| Tax label / standard rate | GST 10% | VAT 20% | Sales tax (destination-based) |
| Tax calc | Flat 10% inclusive | Flat 20% inclusive | **Stripe Tax** by ship-to state/ZIP |
| Date format | DD/MM/YYYY | DD/MM/YYYY | MM/DD/YYYY |
| Cancellation regime | Consumer Guarantees (no cooling-off) | 14-day cooling-off | No general distance-selling cooling-off |
| Timezone | seller-set; default Australia/Melbourne | seller-set; default Europe/London | seller-set; default America/New_York |
| Phone format (SMS) | +61 | +44 | +1 |

> **Timezone is seller-level, not market-level.** The US spans multiple zones, and AU does too (Melbourne vs Perth vs Brisbane, plus DST differences). `markets.timezone_default` is only a fallback when a seller hasn't set `sellers.timezone`. All time-based UI (hold-expiry countdowns, show times, sale-event end times) renders in the seller's TZ. `date_format` stays market-level.

---

## 3. Tax handling

### Display rules (legal requirement, not preference)
- **AU & UK:** prices shown **tax-inclusive**. Store `price_cents` as the **gross** consumer price; compute the tax component for the invoice line.
- **US:** show price **tax-exclusive**; add sales tax at Stripe Checkout. Destination-based, varies by state/county — **never hardcode a rate; use Stripe Tax** with the shopper's shipping address. The on-screen live price is pre-tax.

### Per-product tax class (resolves the v1 flat-rate gap)
A single market rate is wrong: UK has reduced (5%) and zero-rated/exempt categories (children's clothing, books, most food); AU has GST-free items (basic food, health, education); the US needs product tax codes for accurate Stripe Tax calc.

```sql
alter table products
  add column tax_class text not null default 'standard',  -- 'standard' | 'reduced' | 'zero' | 'exempt'
  add column stripe_tax_code text;                         -- US: product tax code for Stripe Tax
```

Effective rate = per-market mapping of `tax_class` → rate (e.g. UK `zero` ⇒ 0%, `reduced` ⇒ 0.05, else `standard_tax_rate`).

### Invoice rounding rule (resolves the reconciliation gap)
For tax-inclusive markets the **gross price is the source of truth**. Per line:
```
tax_cents = round_half_up( gross_cents * rate / (1 + rate) )   -- AU rate=0.10 ⇒ ÷11; UK rate=0.20 ⇒ ÷6
net_cents = gross_cents - tax_cents
```
Round **per line**, then sum; never round the order total independently. The invoice tax total = Σ line `tax_cents`, which reconciles exactly because `net = gross − tax` is derived, not independently rounded. (US: Stripe Tax owns rounding.)

---

## 4. Consumer-law copy (auto-injected by market)

Store as versioned, templated strings keyed by `market_code` (versioned resource files, not a DB table — they need lawyer sign-off and change control). Injected into: claim confirmation DM, invoice, checkout footer, **and every overstock listing + checkout (§8)**. Reworded summaries below — **final copy must be lawyer-reviewed; treat as drafting guidance, not legal advice.**

> **Distance-selling note:** the always-on overstock store (§8) is unambiguously distance selling, so this copy must render on overstock listings and their checkout, not only the live flow.

### 🇦🇺 Australia
- No general right to change your mind on online purchases. Overseas sellers must comply with the ACL when selling to Australians; domestically all sellers must meet the Consumer Guarantees.
- Required framing: goods must match description, be of acceptable quality, and fit for purpose; refunds/repairs/replacements apply where guarantees fail.
- **Live-selling caution:** because there is no buyer's-remorse cooling-off, make claim → payment intent explicit on-screen so impulse claims are informed.

### 🇬🇧 United Kingdom
- Buyers get a **14-day cooling-off** cancellation right, no reason required; refund due within 14 days of notice.
- Pre-contract info must be clear before purchase; confirmation on a durable medium, including the right to cancel and the total price including taxes.
- **Exemptions to flag per-product:** personalised/made-to-spec goods, sealed hygiene items once unsealed, and digital content already downloaded with consent.

### 🇺🇸 United States
- **No general internet cooling-off** — the FTC Cooling-Off Rule is for door-to-door/off-premises sales. Returns are governed by the seller's posted policy + the FTC Mail/Internet Order Rule (shipping timeframes).
- Required: clear posted return policy per seller; sales tax shown at checkout, not in live price.
- **State variance:** keep return-policy copy seller-editable per state where needed.

---

## 5. Buyer locality & order-market resolution

**Default is local-only** (most sellers don't ship internationally). This makes the seller-driven model correct by construction; cross-border is a bounded opt-in.

### Effective ship-to set (single source of truth)
```
allowed_markets(seller) =
    seller.ships_internationally
      ? coalesce(seller.allowed_ship_to_markets, ALL_ENABLED_MARKETS)
      : [ seller.market_code ]            -- local-only default
```

### Order-market resolution (authoritative — governs tax, price display, legal copy)
> **Local-only (default, `ships_internationally = false`):** `order.market_code = seller.market_code`. Currency, tax, price display, and legal copy resolve from the **seller's** market. No FX.
>
> **Cross-border (`ships_internationally = true`):** `order.market_code = market of the buyer's ship-to country` (must be in `allowed_markets(seller)`). Tax, price display, and legal copy resolve from the **destination** market. Payout stays in the seller's currency; FX disclosed at checkout (§7).

The claim engine stays market-neutral in both modes; only checkout-time resolution differs.

### Hard locality gate (enforcement point = checkout)
A "SOLD"/"DIBS" claim is a public comment anyone worldwide can post, so locality is **not** enforced at claim time. It is enforced at Stripe Checkout:
```
shipping_address_collection.allowed_countries = ISO_COUNTRIES( allowed_markets(seller) )
```
A buyer outside the allowed set cannot complete checkout.

### Ineligible-claim / hold-release flow
Prevents foreign claims from silently locking inventory:
1. **Claim accepted as normal** — a hold is created; locality is unknown at this point.
2. **Checkout blocks** an ineligible ship-to via `allowed_countries`.
3. **Hold released** (unit returns to the sellable pool / overstock §8) on the earliest of: buyer abandons/fails the locality check, **or** hold-expiry elapses.
4. **Shopper feedback:** e.g. *"This seller ships within {market.display_name} only."*
5. **Re-sale:** released item is immediately re-claimable.

---

## 6. Platform availability gating (per market)

```sql
create table market_platforms (
  market_code text references markets(code),
  platform    text,                -- facebook | instagram | tiktok | web
  status      text,                -- 'live' | 'beta' | 'coming_soon' | 'unavailable'
  ingest_method text,              -- 'graph_api' | 'tiktok_live_api' | 'native'
  primary key (market_code, platform)
);
```

| Market | Facebook/IG | TikTok Shop | Owned web player |
| :--- | :--- | :--- | :--- |
| 🇦🇺 AU | ✅ live (Graph API) | ⚠️ `coming_soon` — gate OFF, show banner, offer cross-border note | ✅ live |
| 🇬🇧 UK | ✅ live | ✅ live | ✅ live |
| 🇺🇸 US | ✅ live | ✅ live | ✅ live |

> **Status vocabulary reconciled:** a single `market_platforms.status` enum (`'live'|'beta'|'coming_soon'|'unavailable'`) — no separate `tiktok_status` field.

**AU strategy baked in:** default AU sellers to **Facebook/Instagram + owned web player**, with a TikTok `coming_soon` banner and optional **cross-border mode** (sell into US/UK TikTok Shop, §5). Flip `market_platforms` AU/tiktok → `live` the day it launches — zero deploy.

---

## 7. Payment routing (per market)

- **Stripe Connect Express** in all three; connected-account country = seller's `market_code`. Stripe handles settlement and, for the US, **Stripe Tax** for destination sales tax.
- **FX boundary:**
  - *Local-only sellers (default):* payout currency = market currency; buyer pays the same currency. **No FX exposure** — true by design (ship-to restricted to the seller's market).
  - *Cross-border sellers (opt-in):* buyer is presented the destination-market currency; Stripe converts to the seller's payout currency, with FX **disclosed at checkout**. Destination tax per the destination market. *(Exact presentment-vs-settlement currency and TikTok Shop cross-border settlement path: finalise during cross-border build.)*
- SMS invoice fallback (Twilio) uses the market dialling code; Messenger/IG DM is primary.
- **MilvoTech hard rules:** Stripe-hosted checkout only; never store card data; never enter payment on a shopper's behalf.

---

## 8. Overstock storefront (always-on web store)

Turns the owned web player into a persistent store: unsold live inventory becomes a fixed-price storefront with optional time-boxed sale events and Best Offer. It is a **second entry point into the existing hold → invoice → Stripe checkout pipeline** — it inherits §3 tax, §4 legal copy, §5 locality gating, and §7 payments for near-free.

### Listing channel + lifecycle
```sql
alter table products
  add column listing_type      text not null default 'live_only',  -- 'live_only'|'overstock'|'both'
  add column overstock_status  text,            -- 'draft'|'active'|'paused'|'sold_out'|'ended'
  add column overstock_price_cents int,         -- gross, market currency (inclusive AU/UK, exclusive US)
  add column overstock_qty     int not null default 0;
```

### Auto-overstock loop (the retention play)
> On `show.ended`, for products with `listing_type IN ('overstock','both')` or seller `auto_list_overstock = true`: compute `remaining = units − (paid + active_holds)`; if `> 0`, set `overstock_qty = remaining`, `overstock_status = 'active'`, default price = live price unless overridden. The product appears on the always-on storefront — no manual relisting. Released holds (§5) return units here when overstock is active.

### Buy It Now (fixed price)
> A storefront purchase creates a hold and routes to Stripe Checkout via the same pipeline as a live claim — only the trigger differs (a "Buy" tap, not a comment). Order-market resolution, tax/price display, legal copy, and ship-to gating are **identical to §5/§3/§4**.

### Time-boxed Sale / Clearance events ("eBay-type sale")
```sql
create table sale_events (
  id uuid primary key,
  seller_id uuid not null references sellers(id),
  name text not null,
  starts_at timestamptz not null,
  ends_at   timestamptz not null,
  discount_type  text not null,   -- 'percent'|'fixed'|'price_override'
  discount_value numeric,
  status text not null default 'scheduled'  -- 'scheduled'|'active'|'ended'
);
create table sale_event_items (
  sale_event_id uuid references sale_events(id),
  product_id    uuid references products(id),
  sale_price_cents int,           -- resolved markdown; null ⇒ derive from discount_type/value
  primary key (sale_event_id, product_id)
);
```
> While active and within `[starts_at, ends_at]`, the storefront shows `sale_price_cents` and reverts after `ends_at`. Sale price is gross/market-resolved (§3). Countdown renders in the **seller's** timezone (§9).

### Best Offer (negotiation without an auction engine)
```sql
create table offers (
  id uuid primary key,
  product_id uuid not null references products(id),
  buyer_ref  text not null,
  offer_price_cents int not null,
  status text not null default 'pending',  -- 'pending'|'accepted'|'declined'|'countered'|'expired'
  counter_price_cents int,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);
```
> Gated by `sellers.accept_best_offers`. Buyer proposes → seller accepts/counters/declines. On accept, create a hold and issue a checkout link at the agreed price through the standard pipeline. Expired/declined offers hold no inventory.

### Auctions: out of scope for now
> True bidding (proxy bids, anti-sniping, live timers, settlement, disputes) is deferred. Beyond engine cost, **online auctions are NOT exempt from the UK 14-day cooling-off** (unlike traditional public auctions), so auctioned overstock would still owe UK buyers cancellation rights. Best Offer covers most of the value without the complexity. Revisit only if a LiveDibs-owned discovery surface (where LiveDibs supplies demand) justifies it.

---

## 9. i18n / formatting layer

- Use `Intl.NumberFormat(locale, {style:'currency', currency})` for every price — never string-concat a symbol.
- Use `Intl.DateTimeFormat(locale, {timeZone: seller.timezone})` for all dates/countdowns — resolve the **seller's** TZ (§2), not a market default.
- Claim keywords default to English (`SOLD`/`DIBS`) but are **seller-configurable** per show (`SNAP`, `MINE`, etc.).
- All legal/UI strings live in versioned per-market resource bundles, not inline (§4).

---

## 10. Acceptance tests (consolidated)

### Localisation core
- [ ] AU seller: live price GST-inclusive in AUD; invoice shows GST (gross ÷ 11); no cooling-off copy.
- [ ] UK seller: price VAT-inclusive in GBP; invoice shows VAT (gross ÷ 6); 14-day cancellation notice on confirmation + checkout.
- [ ] US seller: live price tax-exclusive in USD; Stripe Tax adds correct state tax at checkout by ship-to; no cooling-off claim.
- [ ] Currency, date, and phone formats all resolve from `market_code`/seller TZ, verified for all three.
- [ ] UK personalised / unsealed-hygiene product correctly flagged cooling-off-exempt.
- [ ] Per-product `tax_class`: UK zero-rated book computes 0% VAT; AU GST-free item computes 0% GST.
- [ ] Invoice line tax components reconcile exactly to the order total after per-line rounding.
- [ ] Time-based UI renders in the seller's timezone (US Pacific seller's hold-expiry shows correct local time).

### Platform & locality
- [ ] AU TikTok ingest gated OFF (`coming_soon`); FB/IG + web active.
- [ ] Flipping `market_platforms` AU/tiktok → `live` enables TikTok with zero deploy.
- [ ] Local-only seller: checkout offers shipping ONLY to the seller's country; foreign ship-to rejected.
- [ ] Non-local commenter claims → hold created, checkout blocked, hold RELEASED (abandon/expiry), shopper sees "ships within {market} only".
- [ ] Cross-border seller: allowed ship-to countries expand; tax + price display + legal copy resolve from the DESTINATION market.

### Overstock storefront
- [ ] Show ends with unsold units + `auto_list_overstock` → units appear on the storefront at `overstock_qty` = remaining, live price by default.
- [ ] Buy It Now creates a hold and completes via Stripe Checkout, with tax/legal/locality identical to a live order.
- [ ] Local-only overstock checkout rejects a foreign ship-to (gating holds on the storefront).
- [ ] Sale event shows the markdown only within `[starts_at, ends_at]` in the seller's TZ, reverts after.
- [ ] Accepted Best Offer issues a checkout link at the agreed price; declined/expired offer holds no inventory.
- [ ] UK overstock listing renders pre-contract info + 14-day cancellation copy on listing and checkout.

---

## 11. Open decisions for Steve

- **Launch order:** AU-first (FB/IG + web, home turf, TikTok gap = differentiator) then UK/US where TikTok Shop is mature? Or US-first for size?
- **Cross-border default:** confirm `ships_internationally = false` for all sellers at launch (recommended), with cross-border as a later opt-in for the ~20 AU brands already selling abroad.
- **Overstock defaults:** ship `auto_list_overstock` **off** (opt-in) and prompt after a seller's 2nd–3rd live? And gate the always-on store + Sale events to the **Pro pricing tier** (it earns revenue without going live — a clear upgrade driver).
- **Sale events + live keywords:** can a Sale-event item also be claimed by comment if the seller goes live during the event, or is it web-only?
- **Legal review:** the §4 strings need per-jurisdiction sign-off before any live sale — budget a one-time review.
- **NZ/CA/SG next?** Schema already supports them; add `markets` rows.

---

## Appendix — change history
- **v1 → v1.1:** buyer-locality model (local-only default + cross-border opt-in), order-market resolution rule, checkout locality gate, ineligible-claim hold-release, FX-boundary clarification, status-enum reconcile.
- **v1.1 → v1.2:** overstock storefront (listing types, auto-relist loop, Buy It Now, Sale events, Best Offer), auctions deferred (UK cooling-off rationale), storefront legal-copy rendering.
- **Consolidation (v2.0):** resolved carried-over items — per-product `tax_class`, seller-level timezone, invoice-rounding rule; dropped redundant `currency_symbol`; renamed `tax_rate_default` → `standard_tax_rate`.

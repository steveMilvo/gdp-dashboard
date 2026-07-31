# Product Factory

An agentic pipeline that takes a niche hypothesis and produces a validated,
packaged, listed and actively marketed digital product. Owned code, owned data
model, owned hosting — not a no-code wrapper.

Australian entity: storage is region-checked at boot and the process refuses to
start against a non-AU region unless the override is set deliberately.

---

## The thesis this is built on

Product creation is not the bottleneck — AI collapsed that to hours. The
bottleneck is **demand discovery** and **content volume**. So the expensive
components here are Agent 1 (demand mining) and Agent 6 (content), and Agent 4
(artifact generation) is deliberately the least interesting part of the system.

Two places this departs from the source material, both on purpose:

- **Cold start is the default assumption.** The usual advice ("post
  consistently") presupposes an existing audience. With no distribution, that
  is not a strategy. Agent 6 therefore biases toward `direct_reply` pieces —
  written to be posted into *the actual threads the complaint came from*, which
  Agent 1 already captured the URLs of. That is the one distribution channel a
  cold start reliably has.
- **The buyer record outlives the transaction.** Every product in the source
  material is a one-time sale, so revenue resets monthly. `buyer` carries
  lifetime value and consent and is the intended seed of a recurring offer.

---

## Architecture

Seven agents, one orchestration spine, one relational store.

| # | Agent | Does | Gate |
|---|-------|------|------|
| 1 | Demand Miner | Scrapes and ranks complaint signal across 5 source kinds | — |
| 2 | Offer Synthesiser | Clusters signal into candidate offers with competitors and prices | **Stage 2** |
| 3 | Validation Runner | Pre-sell page, outreach variants, pre-registered threshold | **Stage 2** |
| 4 | Artifact Builder | Format-specific generation + deterministic quality pass | — |
| 5 | Storefront Publisher | Listing from the objection log, checkout, delivery, receipt | **Stage 4** |
| 6 | Content Engine | Calendar anchored to signal quotes, specificity-gated | **Stage 6** |
| 7 | Signal Loop | Attributes revenue to signals, promotes and demotes | — |

Everything not marked with a gate runs unattended.

### The attribution chain

```
order → listing → product → offer_candidate → signal_cluster
      → pain_signal → source_document
```

Fully joinable, and queryable in one statement (`attribution.ATTRIBUTION_SQL`).
This is the differentiator: it tells you *which observed human complaint*
generated revenue and links to the URL where it was made — not which creative
won.

### Invariants worth knowing

| Invariant | Enforced by |
|---|---|
| A pain signal must recur ≥N times across ≥2 independent source kinds | `demand_miner.mine` |
| Quotes must be verbatim from a captured source row | `demand_miner._extract` — non-verbatim quotes are dropped |
| Every content piece answers exactly one pain signal | `content_piece.pain_signal_id` NOT NULL |
| No artifact ships without a mechanical quality pass | `quality.run_checks` sets the flag; `storefront_publisher` refuses without it |
| A retry never double-posts or double-charges | unique `(adapter, idempotency_key)` on `order` and `publication` |
| Secrets never enter a run record | `vault.Secret` refuses to stringify; config holds refs, not values |
| A prompt change is diffable and revertable | `prompts/*.v<N>.md`, version recorded on every invocation |

---

## Getting started

```bash
pip install -e '.[dev]'
cp .env.example .env          # fill in at minimum PF_OPERATOR_TOKEN
export ANTHROPIC_API_KEY=...

python -m product_factory.cli init
NICHE=$(python -m product_factory.cli niche \
  "AU sole traders drowning in month-end reconciliation" \
  --keyword "stripe reconciliation" --keyword "late invoices")

python -m product_factory.cli run full_cycle --niche "$NICHE" \
  --set success_threshold=25 --set target_pieces=30
```

The run stops at the first gate. From there:

```bash
python -m product_factory.cli gates                      # what needs a decision
python -m product_factory.cli approve <gate_id> --set candidate_id=offr_...
python -m product_factory.cli resume <run_id>            # continues unattended
```

Or drive it from the console:

```bash
uvicorn product_factory.web.app:app --port 8000
open http://localhost:8000/console?token=$PF_OPERATOR_TOKEN
```

### Other verbs

```bash
python -m product_factory.cli report <niche_id>    # Agent 7's weekly ranking
python -m product_factory.cli economics            # build cost per product
python -m product_factory.cli attribution [order]  # the full chain
python -m product_factory.cli apps                 # deployed micro-apps
```

### Running without spend

Set `PF_FIXTURES_DIR` to a directory of captured source rows (`reddit.json`,
`forum.json`, …) and sources read from disk instead of the network. The test
suite does exactly this, plus a stub model layer, so all seven acceptance
criteria are executable in CI:

```bash
pytest              # 32 tests, no API key, no network, no spend
```

---

## Workflows

| Workflow | Phase | Steps |
|---|---|---|
| `phase1_build_and_sell` | 1 | build → approve packaging → publish |
| `discover_demand` | 2 | mine → synthesise → select offer → validation page |
| `full_cycle` | all | the eleven steps, three gates |
| `weekly_signal_loop` | 4 | Agent 7 |

Runs are durable and resumable: every step's output is committed before the
next starts, so `resume_run` replays finished steps from the database rather
than re-executing them. A 40-minute content batch survives a restart, and
calling `resume_run` on a finished run is a no-op.

---

## Storefront and publishing adapters

Agents 1–4 never import a payment SDK. `PF_STOREFRONT` selects between
`selfhosted`, `stripe` (Payment Links) and `gumroad`; all three normalise their
webhooks into one `PaymentEvent`, so `record_order` has a single code path.
Swapping processors is a config change.

Publishing works the same way: a per-platform webhook bridge where one is
configured, and an export queue (JSONL + CSV) where it isn't. The queue is the
honest default — most short-form platforms gate write access behind a partner
agreement.

---

## Micro-app hosting

Micro-app products are generated as single-file, stdlib-only Python servers
against a fixed contract (`/healthz`, `/`, `POST /api/run`), smoke-tested by
actually starting the process and making a request, then deployed to a
per-product subdomain. A registry file drives the emitted nginx config.

**This executes model-generated Python.** A static pass (`micro_app.static_check`)
rejects imports outside an allowlist, `eval`/`exec`/`open`, and dunder attribute
access before anything is written to disk — but it is a static pass, not a
sandbox. Run the app hosts as unprivileged users with no credentials in the
environment, and treat the generated apps as untrusted code you happen to own.

---

## Known limits

- **Scrapers need configuration to be useful.** The adapters ship with sensible
  shapes but no seed URLs, subreddit lists or API keys — those are per-niche
  and belong in the run's `source_config`. The YouTube adapter is fixtures-only
  without a Data API key, and says so rather than silently returning nothing.
- **Grammar checking is heuristic.** `check_prose_hygiene` is a word-count
  floor plus doubled-word and spacing detection, not a language model or a
  LanguageTool integration. It catches what generated prose actually gets
  wrong; it will not catch a subtly wrong comma.
- **Delivery email is best-effort.** If SMTP isn't configured the order is
  still recorded and delivered — the buyer reaches the download from the order
  page — and a `delivery.email_failed` feedback event is written.
- **Refunds are recorded, not initiated.** `adapter.refund()` calls the
  processor; the state change lands when the webhook confirms it.

## Out of scope (deliberately)

Paid advertising, affiliate management, community hosting, localisation,
marketplace syndication. All additive later; none belong in v1.

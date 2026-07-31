"""The web surface: operator console plus the buyer-facing pages.

Three audiences on one app:

* **Operator** (`/console/*`, token-gated) — open gates, run status, unit
  economics, attribution.
* **Prospect** (`/v/{slug}`) — validation landing pages and email capture.
* **Buyer** (`/l/{slug}`, `/checkout/*`, `/download/*`) — listing, checkout,
  delivery.

Webhooks (`/webhooks/{adapter}`) are the delivery trigger. They do the work
inline rather than enqueueing, because the 60-second delivery requirement is
trivially met when the artifact was built and verified before the listing ever
went live.
"""

from __future__ import annotations

import hmac
import logging
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select

from ..agents import validation_runner
from ..agents.signal_loop import funnel_summary
from ..attribution import all_chains, chain_for_order, revenue_by_signal, unit_economics
from ..config import settings
from ..db import init_db, session_scope
from ..llm.pricing import format_microcents
from ..models import (
    ArtifactVersion,
    Listing,
    Niche,
    Order,
    OrderStatus,
    Run,
    ValidationRun,
)
from ..orchestrator import spine, workflows  # noqa: F401 - registers workflows
from ..storefront.adapter import get as get_adapter
from ..storefront.delivery import record_order
from ..vault import resolve
from .render import page

log = logging.getLogger("product_factory.web")

app = FastAPI(title="Product Factory", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------------------------------------------------------- #
# Operator auth
# --------------------------------------------------------------------------- #


def require_operator(request: Request) -> str:
    """Constant-time comparison against a vault-held token. Deliberately not a
    session: the console is a single-operator tool and a bearer token is the
    honest primitive for that."""
    expected = resolve(settings().operator_token_ref, required=False)
    if expected is None:
        raise HTTPException(
            503,
            "PF_OPERATOR_TOKEN is not set; the console is disabled until it is",
        )
    provided = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not provided:
        provided = request.query_params.get("token", "")
    if not hmac.compare_digest(expected.reveal(), provided):
        raise HTTPException(401, "operator token required")
    return "operator"


# --------------------------------------------------------------------------- #
# Console
# --------------------------------------------------------------------------- #


@app.get("/console", response_class=HTMLResponse)
def console(_: str = Depends(require_operator)) -> HTMLResponse:
    gates = spine.open_gates()
    with session_scope() as sess:
        runs = sess.scalars(select(Run).order_by(Run.created_at.desc()).limit(15)).all()
        rows = [
            f"<tr><td><code>{r.id}</code></td><td>{r.workflow}</td>"
            f"<td><span class='pill {r.status}'>{r.status}</span></td>"
            f"<td>{(r.error or '')[:120]}</td></tr>"
            for r in runs
        ]
        econ = unit_economics(sess)

    gate_html = "".join(
        f"<article><h3>Stage {g['stage']}: {g['title']}</h3>"
        f"<p><code>{g['id']}</code> — run <code>{g['run_id']}</code>, "
        f"step <code>{g['step_name']}</code></p>"
        f"<details><summary>Decision payload</summary>"
        f"<pre>{_pre(g['payload'])}</pre></details></article>"
        for g in gates
    ) or "<p>No gates open.</p>"

    econ_html = "".join(
        f"<tr><td>{e['product_name'][:60]}</td><td>{e['model_calls']}</td>"
        f"<td>{e['input_tokens']:,}</td><td>{e['output_tokens']:,}</td>"
        f"<td>{format_microcents(int(e['build_cost_microcents']))}</td></tr>"
        for e in econ
    ) or "<tr><td colspan='5'>No products built yet.</td></tr>"

    return HTMLResponse(
        page(
            "Operator console",
            f"""
<h2>Open gates</h2>{gate_html}
<h2>Recent runs</h2>
<table><thead><tr><th>Run</th><th>Workflow</th><th>Status</th><th>Error</th></tr>
</thead><tbody>{''.join(rows) or "<tr><td colspan='4'>No runs.</td></tr>"}</tbody></table>
<h2>Unit economics (build cost, from the invocation log)</h2>
<table><thead><tr><th>Product</th><th>Calls</th><th>In</th><th>Out</th>
<th>Build cost</th></tr></thead><tbody>{econ_html}</tbody></table>
""",
        )
    )


@app.post("/console/gates/{gate_id}")
def decide(
    gate_id: str, payload: dict[str, Any], _: str = Depends(require_operator)
) -> JSONResponse:
    approved = bool(payload.get("approved", True))
    run_id = spine.decide_gate(
        gate_id,
        approved=approved,
        decision=payload.get("decision", {}),
        operator=payload.get("operator", "operator"),
    )
    status = spine.resume_run(run_id)
    return JSONResponse({"run_id": run_id, "status": status})


@app.post("/console/runs")
def create_run(
    payload: dict[str, Any], _: str = Depends(require_operator)
) -> JSONResponse:
    run_id = spine.start_run(
        payload["workflow"],
        niche_id=payload.get("niche_id"),
        context=payload.get("context", {}),
    )
    status = spine.resume_run(run_id)
    return JSONResponse({"run_id": run_id, "status": status})


@app.get("/console/runs/{run_id}")
def run_detail(run_id: str, _: str = Depends(require_operator)) -> JSONResponse:
    with session_scope() as sess:
        run = sess.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "no such run")
        return JSONResponse(
            {
                "id": run.id,
                "workflow": run.workflow,
                "status": run.status,
                "context": run.context,
                "error": run.error,
                "steps": [
                    {
                        "name": s.name,
                        "status": s.status,
                        "attempt": s.attempt,
                        "output": s.output,
                        "error": (s.error or "")[-800:] or None,
                    }
                    for s in sorted(run.steps, key=lambda s: s.sequence)
                ],
            }
        )


@app.post("/console/runs/{run_id}/resume")
def resume(run_id: str, _: str = Depends(require_operator)) -> JSONResponse:
    return JSONResponse({"run_id": run_id, "status": spine.resume_run(run_id)})


@app.get("/console/attribution")
def attribution(
    order_id: str | None = None, _: str = Depends(require_operator)
) -> JSONResponse:
    with session_scope() as sess:
        rows = chain_for_order(sess, order_id) if order_id else all_chains(sess)
        return JSONResponse({"chains": rows})


@app.get("/console/report/{niche_id}")
def report(niche_id: str, _: str = Depends(require_operator)) -> JSONResponse:
    with session_scope() as sess:
        return JSONResponse(
            {
                "revenue_by_signal": revenue_by_signal(sess, niche_id),
                "funnel": funnel_summary(sess, niche_id),
            }
        )


@app.get("/console/niches")
def niches(_: str = Depends(require_operator)) -> JSONResponse:
    with session_scope() as sess:
        rows = sess.scalars(select(Niche).order_by(Niche.created_at.desc())).all()
        return JSONResponse(
            [
                {
                    "id": n.id,
                    "hypothesis": n.hypothesis,
                    "seed_keywords": n.seed_keywords,
                }
                for n in rows
            ]
        )


# --------------------------------------------------------------------------- #
# Validation landing pages
# --------------------------------------------------------------------------- #


@app.get("/v/{slug}", response_class=HTMLResponse)
def landing(slug: str) -> HTMLResponse:
    with session_scope() as sess:
        validation = sess.scalar(
            select(ValidationRun).where(ValidationRun.slug == slug)
        )
        if validation is None:
            raise HTTPException(404, "no such page")
        validation.views += 1
        body = f"""
<h1>{validation.headline}</h1>
{validation.body_html}
<form method="post" action="/v/{slug}/signup" class="capture">
  <label for="email">Email</label>
  <input id="email" name="email" type="email" required placeholder="you@example.com">
  <button type="submit">{validation.cta_label}</button>
  <p class="fine">Not built yet. You'll get one email when it is, and nothing else.</p>
</form>
"""
        return HTMLResponse(page(validation.headline, body))


@app.post("/v/{slug}/signup")
def signup(slug: str, request: Request, email: str = Form(...)) -> HTMLResponse:
    with session_scope() as sess:
        created = validation_runner.record_signup(
            sess, slug=slug, email=email, referrer=request.headers.get("referer")
        )
    message = (
        "You're on the list. One email when it's ready."
        if created
        else "You were already on the list."
    )
    return HTMLResponse(page("Thanks", f"<h1>Thanks</h1><p>{message}</p>"))


# --------------------------------------------------------------------------- #
# Listings, checkout, delivery
# --------------------------------------------------------------------------- #


@app.get("/l/{slug}", response_class=HTMLResponse)
def listing_page(slug: str, ref: str | None = None) -> HTMLResponse:
    with session_scope() as sess:
        listing = sess.scalar(select(Listing).where(Listing.slug == slug))
        if listing is None or not listing.live:
            raise HTTPException(404, "no such listing")
        price = f"{listing.price_cents / 100:,.2f} {listing.currency}"
        checkout = get_adapter(listing.adapter).checkout_url(slug, ref=ref)
        body = f"""
<h1>{listing.title}</h1>
{listing.description_html}
<p class="price-tag">{price}</p>
<p><a class="button" href="{checkout}">Buy now</a></p>
"""
        return HTMLResponse(page(listing.title, body))


@app.get("/checkout/{slug}", response_class=HTMLResponse)
def checkout(slug: str, ref: str | None = None) -> HTMLResponse:
    """Self-hosted checkout. With `PF_ALLOW_TEST_CHECKOUT=1` this completes the
    purchase directly so the delivery path is exercisable end to end without a
    live processor — which is how acceptance criterion 5 is demonstrated."""
    import os

    with session_scope() as sess:
        listing = sess.scalar(select(Listing).where(Listing.slug == slug))
        if listing is None or not listing.live:
            raise HTTPException(404, "no such listing")
        price = f"{listing.price_cents / 100:,.2f} {listing.currency}"
        test_mode = os.environ.get("PF_ALLOW_TEST_CHECKOUT") == "1"
        action = f"/checkout/{slug}/complete" if test_mode else "#"
        note = (
            "<p class='fine'>Test checkout is enabled — no payment is taken.</p>"
            if test_mode
            else "<p class='fine'>Connect a payment processor to enable checkout.</p>"
        )
        body = f"""
<h1>Checkout — {listing.title}</h1>
<p class="price-tag">{price}</p>
<form method="post" action="{action}">
  <input type="hidden" name="ref" value="{ref or ''}">
  <label for="email">Email for delivery</label>
  <input id="email" name="email" type="email" required>
  <button type="submit" {'' if test_mode else 'disabled'}>Pay {price}</button>
</form>
{note}
"""
        return HTMLResponse(page(f"Checkout — {listing.title}", body))


@app.post("/checkout/{slug}/complete")
def complete_test_checkout(
    slug: str, email: str = Form(...), ref: str = Form("")
) -> RedirectResponse:
    import os

    if os.environ.get("PF_ALLOW_TEST_CHECKOUT") != "1":
        raise HTTPException(403, "test checkout is disabled")

    from ..storefront.selfhosted import test_event

    with session_scope() as sess:
        listing = sess.scalar(select(Listing).where(Listing.slug == slug))
        if listing is None:
            raise HTTPException(404, "no such listing")
        event = test_event(
            listing_slug=slug,
            buyer_email=email,
            amount_cents=listing.price_cents,
            ref=ref or None,
        )
        result = record_order(sess, event)
    return RedirectResponse(f"/orders/{result.order_id}", status_code=303)


@app.post("/webhooks/{adapter_name}")
async def webhook(adapter_name: str, request: Request) -> JSONResponse:
    body = await request.body()
    adapter = get_adapter(adapter_name)
    event = adapter.parse_webhook(dict(request.headers), body)
    if event is None:
        # Unverified or uninteresting. 202 rather than 400 so a legitimate
        # sender doesn't get into a retry loop over an event type we ignore.
        return JSONResponse({"ignored": True}, status_code=202)
    with session_scope() as sess:
        result = record_order(sess, event)
    return JSONResponse(
        {"order_id": result.order_id, "created": result.created, "detail": result.detail}
    )


@app.get("/orders/{order_id}", response_class=HTMLResponse)
def order_page(order_id: str) -> HTMLResponse:
    with session_scope() as sess:
        order = sess.get(Order, order_id)
        if order is None:
            raise HTTPException(404, "no such order")
        listing = sess.get(Listing, order.listing_id)
        assert listing is not None
        if order.status == OrderStatus.REFUNDED.value:
            body = "<h1>Refunded</h1><p>This order has been refunded and access revoked.</p>"
        else:
            body = f"""
<h1>Thanks — {listing.title}</h1>
<p><a class="button" href="/download/{order.download_token}">Download</a></p>
<p>Licence key: <code>{order.licence_key}</code></p>
<p class="fine">Order {order.id} · {order.amount_cents / 100:,.2f} {order.currency}</p>
"""
        return HTMLResponse(page("Your order", body))


@app.get("/download/{download_token}")
def download(download_token: str) -> FileResponse:
    with session_scope() as sess:
        order = sess.scalar(
            select(Order).where(Order.download_token == download_token)
        )
        if order is None or order.status == OrderStatus.REFUNDED.value:
            raise HTTPException(404, "this download link is not valid")
        listing = sess.get(Listing, order.listing_id)
        assert listing is not None
        artifact = sess.get(ArtifactVersion, listing.artifact_version_id)
        if artifact is None or not artifact.path:
            raise HTTPException(404, "no downloadable artifact for this order")
        order.download_count += 1
        path = Path(artifact.path)
    if not path.is_file():
        raise HTTPException(410, "the artifact file is missing on this host")
    return FileResponse(path, filename=path.name)


@app.get("/thanks/{slug}", response_class=HTMLResponse)
def thanks(slug: str) -> HTMLResponse:
    return HTMLResponse(
        page(
            "Thanks",
            "<h1>Thanks</h1><p>Your download link is on its way by email. "
            "If it hasn't arrived in a few minutes, check your spam folder.</p>",
        )
    )


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


def _pre(value: Any) -> str:
    import json

    text = json.dumps(value, indent=2, default=str)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

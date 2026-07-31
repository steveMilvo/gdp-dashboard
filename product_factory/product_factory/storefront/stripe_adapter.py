"""Stripe adapter.

Uses Payment Links so there is no client-side integration to maintain: create a
product + price + link once per listing, then point the storefront at it. The
webhook path normalises `checkout.session.completed` and `charge.refunded` into
the same `PaymentEvent` the self-hosted adapter emits.

Raw HTTP via httpx rather than the stripe SDK — one fewer dependency, and the
three endpoints we need are stable.
"""

from __future__ import annotations

import hmac
import json
import logging
import time
from hashlib import sha256

import httpx

from ..config import settings
from ..vault import SecretNotFound, resolve
from .adapter import ListingSpec, PaymentEvent, RemoteListing, register

log = logging.getLogger("product_factory.storefront.stripe")

API = "https://api.stripe.com/v1"


class StripeAdapter:
    name = "stripe"

    def _key(self) -> str:
        return resolve("env:PF_STRIPE_SECRET_KEY").reveal()

    def _post(self, path: str, data: dict[str, object]) -> dict:
        resp = httpx.post(
            f"{API}{path}",
            data=data,
            auth=(self._key(), ""),
            timeout=30.0,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"stripe {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def publish(self, spec: ListingSpec) -> RemoteListing:
        product = self._post(
            "/products",
            {
                "name": spec.title[:250],
                "description": _plain(spec.description_html)[:500],
                "metadata[slug]": spec.slug,
            },
        )
        price = self._post(
            "/prices",
            {
                "product": product["id"],
                "unit_amount": spec.price_cents,
                "currency": spec.currency.lower(),
            },
        )
        link = self._post(
            "/payment_links",
            {
                "line_items[0][price]": price["id"],
                "line_items[0][quantity]": 1,
                "metadata[slug]": spec.slug,
                "after_completion[type]": "redirect",
                "after_completion[redirect][url]": (
                    f"{settings().base_url}/thanks/{spec.slug}"
                ),
            },
        )
        return RemoteListing(
            adapter=self.name,
            external_id=link["id"],
            checkout_url=link["url"],
            live=True,
            raw={"product": product["id"], "price": price["id"]},
        )

    def checkout_url(self, listing_slug: str, *, ref: str | None = None) -> str:
        """The Payment Link URL is captured at publish time and stored on the
        listing, so this is a lookup rather than another API call."""
        from sqlalchemy import select

        from ..db import session_scope
        from ..models import Listing

        with session_scope() as sess:
            listing = sess.scalar(select(Listing).where(Listing.slug == listing_slug))
            if listing is None:
                raise KeyError(f"no listing with slug {listing_slug!r}")
            url = listing.checkout_url
        if not url:
            raise RuntimeError(
                f"listing {listing_slug!r} has no Stripe payment link; republish it"
            )
        # Stripe Payment Links pass client_reference_id through to the session,
        # which is how a sale gets attributed back to the content piece.
        return f"{url}?client_reference_id={ref}" if ref else url

    def parse_webhook(
        self, headers: dict[str, str], body: bytes
    ) -> PaymentEvent | None:
        if not _verify(headers.get("stripe-signature", ""), body):
            log.warning("rejected stripe webhook with bad signature")
            return None
        payload = json.loads(body or b"{}")
        kind = payload.get("type")
        obj = payload.get("data", {}).get("object", {})

        if kind == "checkout.session.completed":
            status = "paid"
        elif kind in {"charge.refunded", "charge.refund.updated"}:
            status = "refunded"
        else:
            return None

        metadata = obj.get("metadata") or {}
        slug = metadata.get("slug")
        if not slug:
            log.warning("stripe event %s has no slug metadata", payload.get("id"))
            return None

        details = obj.get("customer_details") or {}
        return PaymentEvent(
            adapter=self.name,
            external_id=obj.get("id", payload.get("id", "")),
            # Stripe event ids are unique per delivery attempt-group, which is
            # exactly the idempotency semantics we want on retries.
            idempotency_key=payload.get("id", obj.get("id", "")),
            listing_slug=slug,
            buyer_email=details.get("email") or obj.get("billing_details", {}).get("email", ""),
            buyer_name=details.get("name"),
            amount_cents=int(obj.get("amount_total") or obj.get("amount") or 0),
            currency=(obj.get("currency") or settings().currency).upper(),
            status=status,
            attributed_content_piece_id=(
                obj.get("client_reference_id") or metadata.get("ref")
            ),
            raw=payload,
        )

    def refund(self, external_id: str) -> bool:
        try:
            self._post("/refunds", {"payment_intent": external_id})
            return True
        except Exception:  # noqa: BLE001
            log.exception("stripe refund failed for %s", external_id)
            return False


def _verify(signature_header: str, body: bytes, tolerance: int = 300) -> bool:
    try:
        secret = resolve("env:PF_STRIPE_WEBHOOK_SECRET").reveal()
    except SecretNotFound:
        log.error("PF_STRIPE_WEBHOOK_SECRET is not set; refusing the webhook")
        return False

    parts = dict(
        piece.split("=", 1) for piece in signature_header.split(",") if "=" in piece
    )
    timestamp = parts.get("t")
    provided = parts.get("v1")
    if not timestamp or not provided:
        return False
    if abs(time.time() - int(timestamp)) > tolerance:
        return False
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, sha256
    ).hexdigest()
    return hmac.compare_digest(expected, provided)


def _plain(html: str) -> str:
    import re

    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


register(StripeAdapter())

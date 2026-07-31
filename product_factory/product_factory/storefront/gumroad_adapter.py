"""Gumroad adapter.

Gumroad's API creates products and returns a short link; its ping webhook is
form-encoded rather than JSON and is verified by a shared `resource_secret`
value we set on the ping subscription.
"""

from __future__ import annotations

import hmac
import logging
from urllib.parse import parse_qs

import httpx

from ..config import settings
from ..vault import SecretNotFound, resolve
from .adapter import ListingSpec, PaymentEvent, RemoteListing, register

log = logging.getLogger("product_factory.storefront.gumroad")

API = "https://api.gumroad.com/v2"


class GumroadAdapter:
    name = "gumroad"

    def _token(self) -> str:
        return resolve("env:PF_GUMROAD_ACCESS_TOKEN").reveal()

    def publish(self, spec: ListingSpec) -> RemoteListing:
        files = {}
        if spec.artifact_path:
            files["file"] = open(spec.artifact_path, "rb")  # noqa: SIM115
        try:
            resp = httpx.post(
                f"{API}/products",
                data={
                    "access_token": self._token(),
                    "name": spec.title[:250],
                    "price": spec.price_cents,
                    "description": spec.description_html,
                    "custom_permalink": spec.slug,
                },
                files=files or None,
                timeout=120.0,
            )
        finally:
            for handle in files.values():
                handle.close()

        if resp.status_code >= 400:
            raise RuntimeError(f"gumroad publish -> {resp.status_code}: {resp.text}")
        product = resp.json().get("product", {})
        return RemoteListing(
            adapter=self.name,
            external_id=product.get("id"),
            checkout_url=product.get("short_url", ""),
            live=bool(product.get("published", True)),
            raw=product,
        )

    def checkout_url(self, listing_slug: str, *, ref: str | None = None) -> str:
        from sqlalchemy import select

        from ..db import session_scope
        from ..models import Listing

        with session_scope() as sess:
            listing = sess.scalar(select(Listing).where(Listing.slug == listing_slug))
            if listing is None:
                raise KeyError(f"no listing with slug {listing_slug!r}")
            url = listing.checkout_url
        if not url:
            raise RuntimeError(f"listing {listing_slug!r} has no Gumroad URL")
        return f"{url}?referrer={ref}" if ref else url

    def parse_webhook(
        self, headers: dict[str, str], body: bytes
    ) -> PaymentEvent | None:
        form = {k: v[0] for k, v in parse_qs(body.decode("utf-8")).items()}
        try:
            expected = resolve("env:PF_GUMROAD_PING_SECRET").reveal()
        except SecretNotFound:
            log.error("PF_GUMROAD_PING_SECRET is not set; refusing the ping")
            return None
        if not hmac.compare_digest(expected, form.get("resource_secret", "")):
            log.warning("rejected gumroad ping with bad resource_secret")
            return None

        slug = form.get("permalink") or form.get("product_permalink", "").rsplit("/", 1)[-1]
        if not slug:
            return None
        refunded = form.get("refunded", "false").lower() == "true"
        return PaymentEvent(
            adapter=self.name,
            external_id=form.get("sale_id", ""),
            idempotency_key=form.get("sale_id", ""),
            listing_slug=slug,
            buyer_email=form.get("email", ""),
            buyer_name=form.get("full_name"),
            amount_cents=int(form.get("price", "0") or 0),
            currency=(form.get("currency") or settings().currency).upper(),
            status="refunded" if refunded else "paid",
            attributed_content_piece_id=form.get("referrer") or None,
            raw=form,
        )

    def refund(self, external_id: str) -> bool:
        resp = httpx.put(
            f"{API}/sales/{external_id}/refund",
            data={"access_token": self._token()},
            timeout=30.0,
        )
        if resp.status_code >= 400:
            log.error("gumroad refund %s -> %s", external_id, resp.status_code)
            return False
        return True


register(GumroadAdapter())

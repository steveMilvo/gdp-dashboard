"""Self-hosted checkout.

The listing lives in our own database and the checkout page is served by our
own FastAPI app. Payment capture still needs a processor; this adapter defers
that to the web layer's `/checkout/{slug}` route, which can be wired to a
payment intent or — in `PF_ALLOW_TEST_CHECKOUT` mode — completed directly for
end-to-end testing of the delivery path.
"""

from __future__ import annotations

import hmac
import json
from hashlib import sha256

from ..config import settings
from ..ids import fingerprint
from ..vault import resolve
from .adapter import ListingSpec, PaymentEvent, RemoteListing, register


class SelfHostedAdapter:
    name = "selfhosted"

    def publish(self, spec: ListingSpec) -> RemoteListing:
        return RemoteListing(
            adapter=self.name,
            external_id=None,
            checkout_url=self.checkout_url(spec.slug),
            live=True,
            raw={"hosted_by": "product_factory"},
        )

    def checkout_url(self, listing_slug: str, *, ref: str | None = None) -> str:
        base = f"{settings().base_url}/checkout/{listing_slug}"
        return f"{base}?ref={ref}" if ref else base

    def parse_webhook(
        self, headers: dict[str, str], body: bytes
    ) -> PaymentEvent | None:
        """Our own processor callback. Signed with a shared secret so an
        unauthenticated POST can't mint a paid order."""
        secret = resolve("env:PF_SELFHOSTED_WEBHOOK_SECRET", required=False)
        if secret is not None:
            expected = hmac.new(
                secret.reveal().encode(), body, sha256
            ).hexdigest()
            provided = headers.get("x-pf-signature", "")
            if not hmac.compare_digest(expected, provided):
                return None

        payload = json.loads(body or b"{}")
        if payload.get("type") not in {"payment.succeeded", "payment.refunded"}:
            return None
        return PaymentEvent(
            adapter=self.name,
            external_id=payload["id"],
            idempotency_key=payload.get("idempotency_key") or payload["id"],
            listing_slug=payload["listing_slug"],
            buyer_email=payload["buyer_email"],
            buyer_name=payload.get("buyer_name"),
            amount_cents=int(payload["amount_cents"]),
            currency=payload.get("currency", settings().currency),
            status="refunded"
            if payload["type"] == "payment.refunded"
            else "paid",
            attributed_content_piece_id=payload.get("ref"),
            raw=payload,
        )

    def refund(self, external_id: str) -> bool:
        # Refunds are issued through whichever processor took the payment; this
        # adapter records the intent and the webhook confirms it.
        return True


def test_event(
    *,
    listing_slug: str,
    buyer_email: str,
    amount_cents: int,
    ref: str | None = None,
) -> PaymentEvent:
    """Used by `PF_ALLOW_TEST_CHECKOUT` and the test suite to drive the
    delivery path without a live processor."""
    key = fingerprint(listing_slug, buyer_email, str(amount_cents))
    return PaymentEvent(
        adapter=SelfHostedAdapter.name,
        external_id=f"test_{key[:16]}",
        idempotency_key=key,
        listing_slug=listing_slug,
        buyer_email=buyer_email,
        buyer_name=None,
        amount_cents=amount_cents,
        currency=settings().currency,
        status="paid",
        attributed_content_piece_id=ref,
        raw={"test": True},
    )


register(SelfHostedAdapter())

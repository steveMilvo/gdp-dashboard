"""Order recording, licence issuance, delivery and receipt.

The 60-second delivery requirement is met by doing the work inline on the
webhook: issue the licence key and download token, send the email, stamp
`delivered_at`. There is no queue to drain because there is nothing slow here —
the artifact already exists, built and quality-passed, before the listing went
live.

Idempotency is a unique constraint on `(adapter, idempotency_key)` rather than
an application-level check, so two concurrent webhook deliveries cannot both
create an order.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..ids import token
from ..models import (
    Buyer,
    FeedbackEvent,
    Listing,
    Order,
    OrderStatus,
    utcnow,
)
from ..vault import SecretNotFound, resolve
from .adapter import PaymentEvent

log = logging.getLogger("product_factory.delivery")


@dataclass
class DeliveryResult:
    order_id: str
    created: bool
    delivered: bool
    detail: str


def record_order(session: Session, event: PaymentEvent) -> DeliveryResult:
    listing = session.scalar(
        select(Listing).where(Listing.slug == event.listing_slug)
    )
    if listing is None:
        raise KeyError(f"no listing with slug {event.listing_slug!r}")

    existing = session.scalar(
        select(Order).where(
            Order.adapter == event.adapter,
            Order.idempotency_key == event.idempotency_key,
        )
    )

    if event.status == "refunded":
        return _refund(session, existing, event)

    if existing is not None:
        # A retried webhook. Re-deliver only if the first attempt didn't get
        # that far; never re-charge, never duplicate the buyer record.
        if existing.delivered_at is None:
            _deliver(session, existing, listing)
            return DeliveryResult(existing.id, False, True, "re-delivered on retry")
        return DeliveryResult(existing.id, False, False, "duplicate webhook ignored")

    buyer = _upsert_buyer(session, event)
    order = Order(
        listing_id=listing.id,
        buyer_id=buyer.id,
        adapter=event.adapter,
        external_id=event.external_id,
        idempotency_key=event.idempotency_key,
        amount_cents=event.amount_cents,
        currency=event.currency,
        status=OrderStatus.PAID.value,
        attributed_content_piece_id=event.attributed_content_piece_id,
    )
    session.add(order)
    try:
        session.flush()
    except IntegrityError:
        # Lost the race with a concurrent delivery of the same webhook.
        session.rollback()
        order = session.scalar(
            select(Order).where(
                Order.adapter == event.adapter,
                Order.idempotency_key == event.idempotency_key,
            )
        )
        assert order is not None
        return DeliveryResult(order.id, False, False, "concurrent duplicate ignored")

    buyer.lifetime_value_cents += event.amount_cents
    buyer.last_order_at = utcnow()

    _deliver(session, order, listing)
    session.add(
        FeedbackEvent(
            kind="order.paid",
            listing_id=listing.id,
            order_id=order.id,
            content_piece_id=event.attributed_content_piece_id,
            value=float(event.amount_cents),
            payload={"adapter": event.adapter, "currency": event.currency},
        )
    )
    session.flush()
    return DeliveryResult(order.id, True, True, "delivered")


def _upsert_buyer(session: Session, event: PaymentEvent) -> Buyer:
    buyer = session.scalar(select(Buyer).where(Buyer.email == event.buyer_email))
    if buyer is None:
        buyer = Buyer(email=event.buyer_email, name=event.buyer_name)
        session.add(buyer)
        session.flush()
    elif event.buyer_name and not buyer.name:
        buyer.name = event.buyer_name
    return buyer


def _deliver(session: Session, order: Order, listing: Listing) -> None:
    order.licence_key = order.licence_key or _licence_key()
    order.download_token = order.download_token or token(24)
    order.download_expires_at = None  # lifetime access; revocable per order
    order.status = OrderStatus.DELIVERED.value
    session.flush()

    url = f"{settings().base_url}/download/{order.download_token}"
    subject = f"Your download: {listing.title}"
    body = _receipt_text(order, listing, url)
    sent = _send_email(order.buyer.email, subject, body)
    order.delivered_at = utcnow()
    session.flush()
    if not sent:
        # Delivery is still recorded — the buyer can reach the download from
        # the thank-you page — but the operator needs to know email failed.
        session.add(
            FeedbackEvent(
                kind="delivery.email_failed",
                order_id=order.id,
                listing_id=listing.id,
                payload={"email": order.buyer.email},
            )
        )


def _refund(
    session: Session, order: Order | None, event: PaymentEvent
) -> DeliveryResult:
    if order is None:
        return DeliveryResult("", False, False, "refund for unknown order ignored")
    if order.status == OrderStatus.REFUNDED.value:
        return DeliveryResult(order.id, False, False, "duplicate refund ignored")
    order.status = OrderStatus.REFUNDED.value
    order.refunded_at = utcnow()
    order.download_token = None  # revoke access
    order.buyer.lifetime_value_cents = max(
        0, order.buyer.lifetime_value_cents - order.amount_cents
    )
    session.add(
        FeedbackEvent(
            kind="order.refunded",
            order_id=order.id,
            listing_id=order.listing_id,
            content_piece_id=order.attributed_content_piece_id,
            value=float(-order.amount_cents),
            payload={"adapter": event.adapter},
        )
    )
    session.flush()
    return DeliveryResult(order.id, False, False, "refunded")


def _licence_key() -> str:
    raw = token(12).upper().replace("_", "").replace("-", "")[:16].ljust(16, "X")
    return "-".join(raw[i : i + 4] for i in range(0, 16, 4))


def _receipt_text(order: Order, listing: Listing, url: str) -> str:
    amount = order.amount_cents / 100
    return (
        f"Thanks for buying {listing.title}.\n\n"
        f"Download: {url}\n"
        f"Licence key: {order.licence_key}\n\n"
        f"Order {order.id}\n"
        f"Amount: {amount:,.2f} {order.currency}\n"
        f"Date: {utcnow():%d %b %Y}\n\n"
        "This receipt is issued by an Australian entity. GST treatment depends "
        "on your registration status; the tax invoice, where applicable, is "
        "available from your order page.\n\n"
        f"Order page: {settings().base_url}/orders/{order.id}\n"
    )


def _send_email(to: str, subject: str, body: str) -> bool:
    host = resolve("env:PF_SMTP_HOST", required=False)
    if host is None:
        log.info("SMTP not configured; skipping email to %s (subject=%r)", to, subject)
        return False
    sender = resolve("env:PF_SMTP_FROM", required=False)
    user = resolve("env:PF_SMTP_USER", required=False)
    password = resolve("env:PF_SMTP_PASSWORD", required=False)
    port = int((resolve("env:PF_SMTP_PORT", required=False) or _Fake("587")).reveal())

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender.reveal() if sender else "no-reply@localhost"
    message["To"] = to
    message.set_content(body)

    try:
        with smtplib.SMTP(host.reveal(), port, timeout=20) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if user and password:
                smtp.login(user.reveal(), password.reveal())
            smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError, SecretNotFound):
        log.exception("failed to send delivery email to %s", to)
        return False


class _Fake:
    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

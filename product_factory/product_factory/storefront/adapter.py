"""Storefront adapter contract.

Agents 1-4 never import a payment SDK. They hand a `ListingSpec` to whatever
adapter is configured and get back a `RemoteListing`. Swapping self-hosted
checkout for Stripe or Gumroad is a config change, not a code change — which is
the whole point of putting a seam here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ListingSpec:
    slug: str
    title: str
    description_html: str
    price_cents: int
    currency: str
    preview_assets: list[str] = field(default_factory=list)
    artifact_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RemoteListing:
    adapter: str
    external_id: str | None
    checkout_url: str
    live: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentEvent:
    """Normalised across adapters so `record_order` has one code path."""

    adapter: str
    external_id: str
    idempotency_key: str
    listing_slug: str
    buyer_email: str
    buyer_name: str | None
    amount_cents: int
    currency: str
    status: str  # paid | refunded | failed
    attributed_content_piece_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class StorefrontAdapter(Protocol):
    name: str

    def publish(self, spec: ListingSpec) -> RemoteListing: ...

    def checkout_url(self, listing_slug: str, *, ref: str | None = None) -> str: ...

    def parse_webhook(
        self, headers: dict[str, str], body: bytes
    ) -> PaymentEvent | None: ...

    def refund(self, external_id: str) -> bool: ...


_REGISTRY: dict[str, StorefrontAdapter] = {}


def register(adapter: StorefrontAdapter) -> StorefrontAdapter:
    _REGISTRY[adapter.name] = adapter
    return adapter


def get(name: str | None = None) -> StorefrontAdapter:
    from ..config import settings

    name = name or settings().storefront_adapter
    if name not in _REGISTRY:
        # Import for side effects; adapters self-register on import.
        from . import gumroad_adapter, selfhosted, stripe_adapter  # noqa: F401
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown storefront adapter {name!r}; have {sorted(_REGISTRY)}"
        ) from exc

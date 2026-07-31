"""Publishing adapters: platform API where available, export-to-queue where not.

Every publish goes through `publish_piece`, which takes the idempotency key
from the content piece id plus the target platform. A retry after a timeout
therefore cannot double-post — the unique constraint on
`(adapter, idempotency_key)` rejects the second insert before any HTTP call is
made.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..ids import fingerprint
from ..models import ContentPiece, Publication, utcnow
from ..vault import SecretNotFound, resolve

log = logging.getLogger("product_factory.publishing")


@dataclass
class PublishOutcome:
    status: str  # published | queued | duplicate | failed
    external_id: str | None = None
    url: str | None = None
    detail: str = ""


@runtime_checkable
class PublishAdapter(Protocol):
    name: str

    def supports(self, platform: str) -> bool: ...

    def publish(self, piece: ContentPiece) -> PublishOutcome: ...


class ExportQueueAdapter:
    """The honest default. Most short-form platforms either have no write API
    or gate it behind a partner agreement, so the realistic path is a queue the
    operator (or a scheduling tool) drains.

    Writes both JSONL and CSV: JSONL for programmatic drains, CSV because every
    scheduling tool on the market imports CSV.
    """

    name = "export_queue"

    def supports(self, platform: str) -> bool:
        return True

    def _queue_dir(self) -> Path:
        path = settings().artifacts_dir / "content_queue"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def publish(self, piece: ContentPiece) -> PublishOutcome:
        record = {
            "content_piece_id": piece.id,
            "pain_signal_id": piece.pain_signal_id,
            "platform": piece.platform,
            "scheduled_for": piece.scheduled_for.isoformat()
            if piece.scheduled_for
            else None,
            "hook": piece.hook,
            "body": piece.body,
            "cta": piece.cta,
            "format_notes": piece.format_notes,
        }
        directory = self._queue_dir()
        with (directory / "queue.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        csv_path = directory / "queue.csv"
        write_header = not csv_path.exists()
        with csv_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(record))
            if write_header:
                writer.writeheader()
            writer.writerow(record)

        return PublishOutcome(
            status="queued", detail=f"appended to {directory / 'queue.jsonl'}"
        )


class WebhookAdapter:
    """Generic outbound POST for platforms reachable through a partner API or a
    self-hosted bridge. Configure `PF_PUBLISH_WEBHOOK_<PLATFORM>` with the URL
    and `PF_PUBLISH_TOKEN_<PLATFORM>` with the bearer token."""

    name = "webhook"

    def supports(self, platform: str) -> bool:
        return self._url(platform) is not None

    def _url(self, platform: str) -> str | None:
        secret = resolve(
            f"env:PF_PUBLISH_WEBHOOK_{platform.upper()}", required=False
        )
        return secret.reveal() if secret else None

    def publish(self, piece: ContentPiece) -> PublishOutcome:
        url = self._url(piece.platform)
        if url is None:
            return PublishOutcome(status="failed", detail="no webhook configured")
        headers = {"Content-Type": "application/json"}
        try:
            bearer = resolve(
                f"env:PF_PUBLISH_TOKEN_{piece.platform.upper()}", required=False
            )
            if bearer:
                headers["Authorization"] = f"Bearer {bearer.reveal()}"
        except SecretNotFound:  # pragma: no cover - defensive
            pass

        payload: dict[str, Any] = {
            "idempotency_key": _key(piece),
            "platform": piece.platform,
            "text": f"{piece.hook}\n\n{piece.body}\n\n{piece.cta}",
            "scheduled_for": piece.scheduled_for.isoformat()
            if piece.scheduled_for
            else None,
            "notes": piece.format_notes,
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        except httpx.HTTPError as exc:
            return PublishOutcome(status="failed", detail=f"{type(exc).__name__}: {exc}")
        if resp.status_code >= 400:
            return PublishOutcome(
                status="failed", detail=f"{resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json() if resp.headers.get("content-type", "").startswith(
            "application/json"
        ) else {}
        return PublishOutcome(
            status="published",
            external_id=data.get("id"),
            url=data.get("url"),
            detail="posted",
        )


_ADAPTERS: list[PublishAdapter] = [WebhookAdapter(), ExportQueueAdapter()]


def adapter_for(platform: str) -> PublishAdapter:
    for adapter in _ADAPTERS:
        if adapter.supports(platform):
            return adapter
    return _ADAPTERS[-1]


def _key(piece: ContentPiece) -> str:
    return fingerprint(piece.id, piece.platform)


def publish_piece(session: Session, piece_id: str) -> PublishOutcome:
    piece = session.get(ContentPiece, piece_id)
    if piece is None:
        raise KeyError(f"no such content piece {piece_id!r}")
    if not piece.approved:
        return PublishOutcome(status="failed", detail="piece is not approved")

    adapter = adapter_for(piece.platform)
    key = _key(piece)

    existing = session.scalar(
        select(Publication).where(
            Publication.adapter == adapter.name, Publication.idempotency_key == key
        )
    )
    if existing is not None:
        return PublishOutcome(
            status="duplicate",
            external_id=existing.external_id,
            url=existing.url,
            detail="already published",
        )

    # Reserve the row *before* the network call. If the process dies between
    # the POST and the commit, the reservation is what stops a retry from
    # posting twice.
    publication = Publication(
        content_piece_id=piece.id,
        platform=piece.platform,
        adapter=adapter.name,
        idempotency_key=key,
        status="in_flight",
    )
    session.add(publication)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return PublishOutcome(status="duplicate", detail="concurrent publish")

    outcome = adapter.publish(piece)
    publication.status = outcome.status
    publication.external_id = outcome.external_id
    publication.url = outcome.url
    if outcome.status in {"published", "queued"}:
        publication.published_at = utcnow()
    session.flush()
    return outcome


def publish_approved(session: Session, *, limit: int = 100) -> dict[str, int]:
    pieces = session.scalars(
        select(ContentPiece)
        .where(ContentPiece.approved.is_(True))
        .order_by(ContentPiece.scheduled_for)
        .limit(limit)
    ).all()
    tally: dict[str, int] = {}
    for piece in pieces:
        outcome = publish_piece(session, piece.id)
        tally[outcome.status] = tally.get(outcome.status, 0) + 1
    return tally

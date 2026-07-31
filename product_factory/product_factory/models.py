"""The relational store.

Two things in here are load-bearing and worth reading before the rest:

1. `content_piece.pain_signal_id` is NOT NULL. A content piece that doesn't
   answer an observed complaint is not a content piece; the schema says so
   rather than a docstring.
2. The attribution chain — order -> listing -> product -> offer_candidate ->
   cluster -> pain_signal -> source_document — is fully joinable. That's what
   lets Agent 7 answer "which human complaint produced this revenue" instead of
   "which creative won".
"""

from __future__ import annotations

import datetime as dt
import enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .ids import new_id


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetimes that survive a round trip through SQLite.

    SQLite has no native timestamp type and hands back naive datetimes, which
    then raise on comparison with `utcnow()`. Rather than sprinkling
    `.replace(tzinfo=...)` across every comparison site — and eventually
    missing one — normalise here: store UTC, return UTC-aware.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC)

    def process_result_value(self, value: dt.datetime | None, dialect):
        if value is None:
            return None
        return (
            value.replace(tzinfo=dt.UTC)
            if value.tzinfo is None
            else value.astimezone(dt.UTC)
        )


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


def _pk(prefix: str) -> Mapped[str]:
    return mapped_column(
        String(48), primary_key=True, default=lambda: new_id(prefix)
    )


def _created() -> Mapped[dt.datetime]:
    return mapped_column(UTCDateTime(timezone=True), default=utcnow, nullable=False)


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class WTPTier(str, enum.Enum):
    """Inferred willingness to pay. Coarse on purpose — the point is ranking,
    not a price."""

    FREE = "free"
    LOW = "low"  # under $20
    MID = "mid"  # $20-$99
    HIGH = "high"  # $100+


class ProductFormat(str, enum.Enum):
    EBOOK = "ebook"
    TEMPLATE_PACK = "template_pack"
    NOTION_SYSTEM = "notion_system"
    MICRO_APP = "micro_app"
    MINI_COURSE = "mini_course"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_GATE = "awaiting_gate"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class GateStatus(str, enum.Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    DELIVERED = "delivered"
    REFUNDED = "refunded"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# Stage 1 — demand
# --------------------------------------------------------------------------- #


class Niche(Base):
    __tablename__ = "niche"

    id: Mapped[str] = _pk("nch")
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    seed_keywords: Mapped[list[Any]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()

    pain_signals: Mapped[list[PainSignal]] = relationship(back_populates="niche")
    clusters: Mapped[list[SignalCluster]] = relationship(back_populates="niche")


class SourceDocument(Base):
    """The captured row behind every claim.

    Marketing copy cites a pain_signal; a pain_signal cites one of these. If a
    sentence in a sales page can't walk back to a row here, it doesn't ship.
    """

    __tablename__ = "source_document"

    id: Mapped[str] = _pk("src")
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[dt.datetime] = _created()

    __table_args__ = (UniqueConstraint("content_hash", name="uq_source_hash"),)


class PainSignal(Base):
    __tablename__ = "pain_signal"

    id: Mapped[str] = _pk("pain")
    niche_id: Mapped[str] = mapped_column(ForeignKey("niche.id"), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    normalised: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    independent_sources: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    wtp_tier: Mapped[str] = mapped_column(String(16), default=WTPTier.LOW.value)
    wtp_rationale: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = _created()

    niche: Mapped[Niche] = relationship(back_populates="pain_signals")
    occurrences: Mapped[list[SignalOccurrence]] = relationship(
        back_populates="pain_signal", cascade="all, delete-orphan"
    )
    content_pieces: Mapped[list[ContentPiece]] = relationship(
        back_populates="pain_signal"
    )

    __table_args__ = (
        UniqueConstraint("niche_id", "fingerprint", name="uq_signal_per_niche"),
        Index("ix_pain_signal_score", "niche_id", "score"),
    )


class SignalOccurrence(Base):
    """One sighting of a signal in one source. Recurrence is COUNT(*) over this
    table, and "independent sources" is COUNT(DISTINCT source_kind) — which is
    why we store sightings rather than just bumping an integer."""

    __tablename__ = "signal_occurrence"

    id: Mapped[str] = _pk("occ")
    pain_signal_id: Mapped[str] = mapped_column(
        ForeignKey("pain_signal.id"), nullable=False
    )
    source_document_id: Mapped[str] = mapped_column(
        ForeignKey("source_document.id"), nullable=False
    )
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = _created()

    pain_signal: Mapped[PainSignal] = relationship(back_populates="occurrences")
    source_document: Mapped[SourceDocument] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "pain_signal_id", "source_document_id", name="uq_occurrence"
        ),
    )


# --------------------------------------------------------------------------- #
# Stage 2 — offers
# --------------------------------------------------------------------------- #


class SignalCluster(Base):
    __tablename__ = "signal_cluster"

    id: Mapped[str] = _pk("clus")
    niche_id: Mapped[str] = mapped_column(ForeignKey("niche.id"), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()

    niche: Mapped[Niche] = relationship(back_populates="clusters")
    members: Mapped[list[ClusterMember]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )
    offer_candidates: Mapped[list[OfferCandidate]] = relationship(
        back_populates="cluster"
    )


class ClusterMember(Base):
    """The many-to-many join that lets one signal feed several offers."""

    __tablename__ = "cluster_member"

    id: Mapped[str] = _pk("cmem")
    cluster_id: Mapped[str] = mapped_column(
        ForeignKey("signal_cluster.id"), nullable=False
    )
    pain_signal_id: Mapped[str] = mapped_column(
        ForeignKey("pain_signal.id"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    cluster: Mapped[SignalCluster] = relationship(back_populates="members")
    pain_signal: Mapped[PainSignal] = relationship()

    __table_args__ = (
        UniqueConstraint("cluster_id", "pain_signal_id", name="uq_cluster_member"),
    )


class OfferCandidate(Base):
    __tablename__ = "offer_candidate"

    id: Mapped[str] = _pk("offr")
    niche_id: Mapped[str] = mapped_column(ForeignKey("niche.id"), nullable=False)
    cluster_id: Mapped[str] = mapped_column(
        ForeignKey("signal_cluster.id"), nullable=False
    )
    promise: Mapped[str] = mapped_column(Text, nullable=False)
    target_buyer: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="AUD")
    rationale: Mapped[str | None] = mapped_column(Text)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = _created()

    cluster: Mapped[SignalCluster] = relationship(back_populates="offer_candidates")
    competitors: Mapped[list[Competitor]] = relationship(
        back_populates="offer_candidate", cascade="all, delete-orphan"
    )
    validation_runs: Mapped[list[ValidationRun]] = relationship(
        back_populates="offer_candidate"
    )
    products: Mapped[list[Product]] = relationship(back_populates="offer_candidate")


class Competitor(Base):
    __tablename__ = "competitor"

    id: Mapped[str] = _pk("comp")
    offer_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("offer_candidate.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="AUD")
    positioning: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_document.id")
    )

    offer_candidate: Mapped[OfferCandidate] = relationship(
        back_populates="competitors"
    )


class NegativeExample(Base):
    """Rejected offers, kept so Agent 2 doesn't re-propose the same dead end
    next week."""

    __tablename__ = "negative_example"

    id: Mapped[str] = _pk("neg")
    niche_id: Mapped[str] = mapped_column(ForeignKey("niche.id"), nullable=False)
    promise: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="gate_rejection")
    created_at: Mapped[dt.datetime] = _created()


# --------------------------------------------------------------------------- #
# Stage 3 — validation
# --------------------------------------------------------------------------- #


class ValidationRun(Base):
    __tablename__ = "validation_run"

    id: Mapped[str] = _pk("val")
    offer_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("offer_candidate.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    cta_label: Mapped[str] = mapped_column(String(120), default="Get early access")
    # Declared before the test runs. Stored so nobody can move the goalposts
    # after seeing the numbers.
    success_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_metric: Mapped[str] = mapped_column(String(32), default="signups")
    threshold_set_at: Mapped[dt.datetime] = _created()
    closes_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    signups: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[dt.datetime] = _created()

    offer_candidate: Mapped[OfferCandidate] = relationship(
        back_populates="validation_runs"
    )
    outreach: Mapped[list[OutreachVariant]] = relationship(
        back_populates="validation_run", cascade="all, delete-orphan"
    )
    objections: Mapped[list[Objection]] = relationship(
        back_populates="validation_run", cascade="all, delete-orphan"
    )
    signup_records: Mapped[list[ValidationSignup]] = relationship(
        back_populates="validation_run", cascade="all, delete-orphan"
    )


class OutreachVariant(Base):
    __tablename__ = "outreach_variant"

    id: Mapped[str] = _pk("out")
    validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("validation_run.id"), nullable=False
    )
    # Aimed at the people whose quote fed the cluster, so we keep the link.
    pain_signal_id: Mapped[str] = mapped_column(
        ForeignKey("pain_signal.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), default="dm")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)

    validation_run: Mapped[ValidationRun] = relationship(back_populates="outreach")
    pain_signal: Mapped[PainSignal] = relationship()


class ValidationSignup(Base):
    __tablename__ = "validation_signup"

    id: Mapped[str] = _pk("vsig")
    validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("validation_run.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    referrer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()

    validation_run: Mapped[ValidationRun] = relationship(
        back_populates="signup_records"
    )

    __table_args__ = (
        UniqueConstraint("validation_run_id", "email", name="uq_signup_email"),
    )


class Objection(Base):
    """Objections are the most valuable output of a validation run — they become
    the FAQ and the rebuttal section of the sales page."""

    __tablename__ = "objection"

    id: Mapped[str] = _pk("obj")
    validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("validation_run.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    theme: Mapped[str | None] = mapped_column(String(64))
    rebuttal: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()

    validation_run: Mapped[ValidationRun] = relationship(back_populates="objections")


# --------------------------------------------------------------------------- #
# Stage 4/5 — product, artifact, listing, order
# --------------------------------------------------------------------------- #


class Product(Base):
    __tablename__ = "product"

    id: Mapped[str] = _pk("prod")
    offer_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("offer_candidate.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = _created()

    offer_candidate: Mapped[OfferCandidate] = relationship(back_populates="products")
    artifact_versions: Mapped[list[ArtifactVersion]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    listings: Mapped[list[Listing]] = relationship(back_populates="product")


class ArtifactVersion(Base):
    __tablename__ = "artifact_version"

    id: Mapped[str] = _pk("art")
    product_id: Mapped[str] = mapped_column(ForeignKey("product.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    bytes: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64))
    cover_path: Mapped[str | None] = mapped_column(Text)
    # No artifact ships without a mechanical pass appropriate to its type.
    quality_passed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = _created()

    product: Mapped[Product] = relationship(back_populates="artifact_versions")
    quality_checks: Mapped[list[QualityCheck]] = relationship(
        back_populates="artifact_version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("product_id", "version", name="uq_artifact_version"),
    )


class QualityCheck(Base):
    __tablename__ = "quality_check"

    id: Mapped[str] = _pk("qc")
    artifact_version_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_version.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()

    artifact_version: Mapped[ArtifactVersion] = relationship(
        back_populates="quality_checks"
    )


class Listing(Base):
    __tablename__ = "listing"

    id: Mapped[str] = _pk("lst")
    product_id: Mapped[str] = mapped_column(ForeignKey("product.id"), nullable=False)
    artifact_version_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_version.id"), nullable=False
    )
    adapter: Mapped[str] = mapped_column(String(32), default="selfhosted")
    external_id: Mapped[str | None] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description_html: Mapped[str] = mapped_column(Text, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="AUD")
    preview_assets: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # Whatever the adapter handed back on publish. Storing it means the rest of
    # the system never has to know which processor is behind the button.
    checkout_url: Mapped[str | None] = mapped_column(Text)
    live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = _created()

    product: Mapped[Product] = relationship(back_populates="listings")
    artifact_version: Mapped[ArtifactVersion] = relationship()
    orders: Mapped[list[Order]] = relationship(back_populates="listing")


class Buyer(Base):
    """Persists beyond the transaction — deliberately. A one-time sale that
    leaves no buyer record is revenue that resets to zero next month."""

    __tablename__ = "buyer"

    id: Mapped[str] = _pk("buyr")
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2))
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    lifetime_value_cents: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[dt.datetime] = _created()
    last_order_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    orders: Mapped[list[Order]] = relationship(back_populates="buyer")


class Order(Base):
    __tablename__ = "order"

    id: Mapped[str] = _pk("ord")
    listing_id: Mapped[str] = mapped_column(ForeignKey("listing.id"), nullable=False)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id"), nullable=False)
    adapter: Mapped[str] = mapped_column(String(32), default="selfhosted")
    external_id: Mapped[str | None] = mapped_column(String(128))
    # Idempotency key: a retried webhook must not double-charge or double-post.
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="AUD")
    status: Mapped[str] = mapped_column(
        String(16), default=OrderStatus.PENDING.value, nullable=False
    )
    licence_key: Mapped[str | None] = mapped_column(String(64))
    download_token: Mapped[str | None] = mapped_column(String(96))
    download_expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    # Where the buyer came from — the far end of the attribution chain.
    attributed_content_piece_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_piece.id")
    )
    refunded_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    delivered_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    created_at: Mapped[dt.datetime] = _created()

    listing: Mapped[Listing] = relationship(back_populates="orders")
    buyer: Mapped[Buyer] = relationship(back_populates="orders")

    __table_args__ = (
        UniqueConstraint("adapter", "idempotency_key", name="uq_order_idem"),
        Index("ix_order_status", "status"),
    )


# --------------------------------------------------------------------------- #
# Stage 6 — content
# --------------------------------------------------------------------------- #


class ContentPiece(Base):
    __tablename__ = "content_piece"

    id: Mapped[str] = _pk("cnt")
    # NOT NULL, and it is the whole point. Content answers a complaint; it does
    # not advertise a product.
    pain_signal_id: Mapped[str] = mapped_column(
        ForeignKey("pain_signal.id"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(ForeignKey("product.id"))
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    cta: Mapped[str] = mapped_column(Text, nullable=False)
    format_notes: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Set when the specificity rule kills a piece; kept rather than deleted so
    # the rejection rate is measurable.
    rejected_reason: Mapped[str | None] = mapped_column(Text)
    specificity_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = _created()

    pain_signal: Mapped[PainSignal] = relationship(back_populates="content_pieces")
    product: Mapped[Product | None] = relationship()
    publications: Mapped[list[Publication]] = relationship(
        back_populates="content_piece", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("pain_signal_id IS NOT NULL", name="ck_content_has_signal"),
    )


class Publication(Base):
    __tablename__ = "publication"

    id: Mapped[str] = _pk("pub")
    content_piece_id: Mapped[str] = mapped_column(
        ForeignKey("content_piece.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    adapter: Mapped[str] = mapped_column(String(32), default="export_queue")
    external_id: Mapped[str | None] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    published_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    engagements: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = _created()

    content_piece: Mapped[ContentPiece] = relationship(back_populates="publications")

    __table_args__ = (
        UniqueConstraint("adapter", "idempotency_key", name="uq_publication_idem"),
    )


# --------------------------------------------------------------------------- #
# Stage 7 — feedback
# --------------------------------------------------------------------------- #


class FeedbackEvent(Base):
    """Everything Agent 7 ingests, in one shape: engagement, conversion,
    refunds, support themes."""

    __tablename__ = "feedback_event"

    id: Mapped[str] = _pk("fbk")
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    pain_signal_id: Mapped[str | None] = mapped_column(ForeignKey("pain_signal.id"))
    content_piece_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_piece.id")
    )
    listing_id: Mapped[str | None] = mapped_column(ForeignKey("listing.id"))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("order.id"))
    value: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[dt.datetime] = _created()

    __table_args__ = (Index("ix_feedback_kind", "kind", "occurred_at"),)


class WeeklyReport(Base):
    __tablename__ = "weekly_report"

    id: Mapped[str] = _pk("rpt")
    niche_id: Mapped[str] = mapped_column(ForeignKey("niche.id"), nullable=False)
    period_start: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    rankings: Mapped[list[Any]] = mapped_column(JSON, default=list)
    promoted: Mapped[list[Any]] = mapped_column(JSON, default=list)
    demoted: Mapped[list[Any]] = mapped_column(JSON, default=list)
    content_patterns: Mapped[list[Any]] = mapped_column(JSON, default=list)
    narrative: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()


# --------------------------------------------------------------------------- #
# Orchestration spine
# --------------------------------------------------------------------------- #


class Run(Base):
    __tablename__ = "run"

    id: Mapped[str] = _pk("run")
    workflow: Mapped[str] = mapped_column(String(64), nullable=False)
    niche_id: Mapped[str | None] = mapped_column(ForeignKey("niche.id"))
    status: Mapped[str] = mapped_column(
        String(16), default=RunStatus.PENDING.value, nullable=False
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    created_at: Mapped[dt.datetime] = _created()

    steps: Mapped[list[RunStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    gates: Mapped[list[Gate]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunStep(Base):
    """One checkpoint. `output` is the resume unit: a completed step is never
    re-executed, so a 40-minute content batch survives a restart."""

    __tablename__ = "run_step"

    id: Mapped[str] = _pk("stp")
    run_id: Mapped[str] = mapped_column(ForeignKey("run.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=StepStatus.PENDING.value, nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))

    run: Mapped[Run] = relationship(back_populates="steps")

    __table_args__ = (UniqueConstraint("run_id", "name", name="uq_run_step"),)


class Gate(Base):
    """A human approval gate. Stages 2, 4 and 6 are mandatory; the spine blocks
    on an open gate rather than proceeding optimistically."""

    __tablename__ = "gate"

    id: Mapped[str] = _pk("gate")
    run_id: Mapped[str] = mapped_column(ForeignKey("run.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(96), nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), default=GateStatus.OPEN.value, nullable=False
    )
    decision: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decided_by: Mapped[str | None] = mapped_column(String(255))
    decided_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(timezone=True))
    created_at: Mapped[dt.datetime] = _created()

    run: Mapped[Run] = relationship(back_populates="gates")

    __table_args__ = (UniqueConstraint("run_id", "step_name", name="uq_gate_step"),)


class AgentInvocation(Base):
    """Every model call. Per-product unit economics must be computable from
    this table alone, so cost is stored in cents at call time rather than
    recomputed later from a price list that will have changed."""

    __tablename__ = "agent_invocation"

    id: Mapped[str] = _pk("inv")
    run_id: Mapped[str | None] = mapped_column(ForeignKey("run.id"))
    step_name: Mapped[str | None] = mapped_column(String(96))
    agent: Mapped[str] = mapped_column(String(48), nullable=False)
    prompt_name: Mapped[str | None] = mapped_column(String(96))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_microcents: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("product.id"))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()

    __table_args__ = (Index("ix_invocation_product", "product_id"),)

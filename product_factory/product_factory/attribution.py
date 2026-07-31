"""The attribution chain.

This is the differentiator. Ad platforms tell you which creative won. This
tells you *which observed human complaint* generated the revenue, and gives you
the URL where that complaint was made.

    order -> listing -> product -> offer_candidate
          -> signal_cluster -> cluster_member -> pain_signal -> source_document

`ATTRIBUTION_SQL` is one statement, deliberately — the acceptance criterion is
that a completed purchase produces a full chain queryable in a single SQL
statement, and a query you have to assemble in Python doesn't count.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

ATTRIBUTION_SQL = text(
    """
SELECT
    o.id                      AS order_id,
    o.created_at              AS purchased_at,
    o.amount_cents            AS amount_cents,
    o.currency                AS currency,
    o.status                  AS order_status,
    b.email                   AS buyer_email,
    l.slug                    AS listing_slug,
    l.title                   AS listing_title,
    p.id                      AS product_id,
    p.format                  AS product_format,
    oc.id                     AS offer_candidate_id,
    oc.promise                AS offer_promise,
    sc.label                  AS cluster_label,
    ps.id                     AS pain_signal_id,
    ps.quote                  AS pain_quote,
    ps.normalised             AS pain_problem,
    ps.recurrence_count       AS pain_recurrence,
    sd.url                    AS source_url,
    sd.source_kind            AS source_kind,
    cp.id                     AS content_piece_id,
    cp.hook                   AS content_hook,
    cp.platform               AS content_platform
FROM "order"           AS o
JOIN listing           AS l  ON l.id  = o.listing_id
JOIN product           AS p  ON p.id  = l.product_id
JOIN offer_candidate   AS oc ON oc.id = p.offer_candidate_id
JOIN signal_cluster    AS sc ON sc.id = oc.cluster_id
JOIN cluster_member    AS cm ON cm.cluster_id = sc.id
JOIN pain_signal       AS ps ON ps.id = cm.pain_signal_id
LEFT JOIN signal_occurrence AS so ON so.pain_signal_id = ps.id
LEFT JOIN source_document   AS sd ON sd.id = so.source_document_id
LEFT JOIN content_piece     AS cp ON cp.id = o.attributed_content_piece_id
JOIN buyer             AS b  ON b.id  = o.buyer_id
WHERE (:order_id IS NULL OR o.id = :order_id)
ORDER BY o.created_at DESC, ps.score DESC
"""
)

# Revenue per pain signal, and per content piece within it. Agent 7's ranking
# is a GROUP BY over the same join, so the two never disagree.
REVENUE_BY_SIGNAL_SQL = text(
    """
SELECT
    ps.id                                        AS pain_signal_id,
    ps.quote                                     AS pain_quote,
    ps.normalised                                AS pain_problem,
    ps.recurrence_count                          AS recurrence,
    ps.score                                     AS signal_score,
    COUNT(DISTINCT cp.id)                        AS content_pieces,
    COUNT(DISTINCT CASE WHEN o.status IN ('paid','delivered')
                        THEN o.id END)           AS orders,
    COALESCE(SUM(CASE WHEN o.status IN ('paid','delivered')
                      THEN o.amount_cents ELSE 0 END), 0) AS gross_cents,
    COALESCE(SUM(CASE WHEN o.status = 'refunded'
                      THEN o.amount_cents ELSE 0 END), 0) AS refunded_cents
FROM pain_signal AS ps
LEFT JOIN content_piece   AS cp ON cp.pain_signal_id = ps.id
LEFT JOIN "order"         AS o  ON o.attributed_content_piece_id = cp.id
WHERE ps.niche_id = :niche_id
GROUP BY ps.id, ps.quote, ps.normalised, ps.recurrence_count, ps.score
ORDER BY gross_cents DESC, ps.score DESC
"""
)

UNIT_ECONOMICS_SQL = text(
    """
SELECT
    p.id                                  AS product_id,
    p.name                                AS product_name,
    COALESCE(SUM(ai.cost_microcents), 0)  AS build_cost_microcents,
    COUNT(ai.id)                          AS model_calls,
    COALESCE(SUM(ai.input_tokens), 0)     AS input_tokens,
    COALESCE(SUM(ai.output_tokens), 0)    AS output_tokens
FROM product AS p
LEFT JOIN agent_invocation AS ai ON ai.product_id = p.id
GROUP BY p.id, p.name
"""
)


def _rows(session: Session, statement, **params: Any) -> list[dict[str, Any]]:
    result = session.execute(statement, params)
    return [dict(row) for row in result.mappings()]


def chain_for_order(session: Session, order_id: str) -> list[dict[str, Any]]:
    """Every complaint that fed the offer this order bought, with sources."""
    return _rows(session, ATTRIBUTION_SQL, order_id=order_id)


def all_chains(session: Session) -> list[dict[str, Any]]:
    return _rows(session, ATTRIBUTION_SQL, order_id=None)


def revenue_by_signal(session: Session, niche_id: str) -> list[dict[str, Any]]:
    return _rows(session, REVENUE_BY_SIGNAL_SQL, niche_id=niche_id)


def unit_economics(session: Session) -> list[dict[str, Any]]:
    """Build cost per product, straight from the invocation log. Revenue joins
    on separately; keeping them apart means a product with no sales still
    reports what it cost to make."""
    return _rows(session, UNIT_ECONOMICS_SQL)

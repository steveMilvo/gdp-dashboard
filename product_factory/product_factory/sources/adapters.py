"""Concrete demand sources.

Five kinds, chosen because they fail differently: Reddit and forums surface
articulated complaint, review sections surface complaint about an existing
paid solution (the strongest willingness-to-pay signal), YouTube comments
surface complaint adjacent to instructional content, and marketplace listings
with high sales but poor ratings surface *proven demand plus a bad incumbent*
— the most valuable shape of all.

Every adapter honours fixtures mode, so an offline run exercises the same
clustering path as a live one.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Fetcher, RawItem, Source

_WHITESPACE = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", _TAGS.sub(" ", text)).strip()


class RedditSource(Source):
    """Public JSON endpoints. No OAuth, which means a low rate ceiling — the
    Fetcher's per-host bucket is doing real work here."""

    kind = "reddit"

    def __init__(self, subreddits: list[str] | None = None) -> None:
        self.subreddits = subreddits or []

    def collect(
        self, query: str, *, limit: int = 50, fetcher: Fetcher | None = None
    ) -> list[RawItem]:
        fixtures = self._fixtures(query)
        if fixtures is not None:
            return fixtures[:limit]

        owned = fetcher is None
        fetcher = fetcher or Fetcher()
        items: list[RawItem] = []
        try:
            targets = self.subreddits or ["all"]
            for sub in targets:
                url = f"https://www.reddit.com/r/{sub}/search.json"
                resp = fetcher.get(
                    url,
                    q=query,
                    restrict_sr=1 if sub != "all" else 0,
                    sort="relevance",
                    limit=min(limit, 100),
                    t="year",
                )
                for child in resp.json().get("data", {}).get("children", []):
                    data = child.get("data", {})
                    body = data.get("selftext") or data.get("body") or ""
                    text = _clean(f"{data.get('title', '')}. {body}")
                    if len(text) < 40:
                        continue
                    items.append(
                        RawItem(
                            source_kind=self.kind,
                            url=f"https://www.reddit.com{data.get('permalink', '')}",
                            title=data.get("title"),
                            author=data.get("author"),
                            text=text,
                            meta={
                                "score": data.get("score", 0),
                                "num_comments": data.get("num_comments", 0),
                                "subreddit": data.get("subreddit"),
                            },
                        )
                    )
        finally:
            if owned:
                fetcher.close()
        return items[:limit]


class ForumThreadSource(Source):
    """Generic HTML thread scraper. Given seed URLs, pull post bodies with a
    configurable selector-ish regex. Deliberately dumb: forum markup varies too
    much to justify a parser per platform at v1."""

    kind = "forum"

    def __init__(self, urls: list[str] | None = None, block_pattern: str | None = None):
        self.urls = urls or []
        self.block_pattern = re.compile(
            block_pattern or r'<div class="post[^"]*"[^>]*>(.*?)</div>', re.S | re.I
        )

    def collect(
        self, query: str, *, limit: int = 50, fetcher: Fetcher | None = None
    ) -> list[RawItem]:
        fixtures = self._fixtures(query)
        if fixtures is not None:
            return fixtures[:limit]

        owned = fetcher is None
        fetcher = fetcher or Fetcher()
        items: list[RawItem] = []
        try:
            for url in self.urls:
                resp = fetcher.get(url)
                for idx, block in enumerate(self.block_pattern.findall(resp.text)):
                    text = _clean(block)
                    if len(text) < 40:
                        continue
                    items.append(
                        RawItem(
                            source_kind=self.kind,
                            url=f"{url}#post-{idx}",
                            text=text,
                            meta={"thread": url},
                        )
                    )
        finally:
            if owned:
                fetcher.close()
        return items[:limit]


class ReviewComplaintSource(Source):
    """Complaint sections of product reviews. Somebody who paid and then
    complained has already proven willingness to pay."""

    kind = "review"

    def __init__(self, endpoints: list[str] | None = None) -> None:
        self.endpoints = endpoints or []

    def collect(
        self, query: str, *, limit: int = 50, fetcher: Fetcher | None = None
    ) -> list[RawItem]:
        fixtures = self._fixtures(query)
        if fixtures is not None:
            return fixtures[:limit]

        owned = fetcher is None
        fetcher = fetcher or Fetcher()
        items: list[RawItem] = []
        try:
            for endpoint in self.endpoints:
                resp = fetcher.get(endpoint, q=query)
                payload: Any = resp.json()
                for review in _iter_reviews(payload):
                    rating = review.get("rating")
                    cons = review.get("cons") or review.get("body") or ""
                    text = _clean(str(cons))
                    if len(text) < 40:
                        continue
                    if isinstance(rating, (int, float)) and rating > 3:
                        continue  # positive reviews are not complaint signal
                    items.append(
                        RawItem(
                            source_kind=self.kind,
                            url=review.get("url", endpoint),
                            author=review.get("author"),
                            text=text,
                            meta={"rating": rating, "product": review.get("product")},
                        )
                    )
        finally:
            if owned:
                fetcher.close()
        return items[:limit]


class YouTubeCommentSource(Source):
    """Comment sections of adjacent videos. Requires a Data API key; without
    one this adapter is fixtures-only, which is stated rather than silently
    returning nothing."""

    kind = "youtube"

    def __init__(self, video_ids: list[str] | None = None, api_key: str | None = None):
        self.video_ids = video_ids or []
        self.api_key = api_key

    def collect(
        self, query: str, *, limit: int = 50, fetcher: Fetcher | None = None
    ) -> list[RawItem]:
        fixtures = self._fixtures(query)
        if fixtures is not None:
            return fixtures[:limit]
        if not self.api_key:
            return []

        owned = fetcher is None
        fetcher = fetcher or Fetcher()
        items: list[RawItem] = []
        try:
            for video_id in self.video_ids:
                resp = fetcher.get(
                    "https://www.googleapis.com/youtube/v3/commentThreads",
                    part="snippet",
                    videoId=video_id,
                    maxResults=min(limit, 100),
                    order="relevance",
                    key=self.api_key,
                )
                for item in resp.json().get("items", []):
                    snippet = (
                        item.get("snippet", {})
                        .get("topLevelComment", {})
                        .get("snippet", {})
                    )
                    text = _clean(snippet.get("textOriginal", ""))
                    if len(text) < 40:
                        continue
                    items.append(
                        RawItem(
                            source_kind=self.kind,
                            url=f"https://www.youtube.com/watch?v={video_id}&lc={item.get('id')}",
                            author=snippet.get("authorDisplayName"),
                            text=text,
                            meta={"likes": snippet.get("likeCount", 0)},
                        )
                    )
        finally:
            if owned:
                fetcher.close()
        return items[:limit]


class MarketplaceListingSource(Source):
    """High sales, poor ratings. The listing description tells you what buyers
    were promised; the ratings tell you it wasn't delivered."""

    kind = "marketplace"

    def __init__(
        self,
        endpoints: list[str] | None = None,
        min_sales: int = 100,
        max_rating: float = 4.0,
    ) -> None:
        self.endpoints = endpoints or []
        self.min_sales = min_sales
        self.max_rating = max_rating

    def collect(
        self, query: str, *, limit: int = 50, fetcher: Fetcher | None = None
    ) -> list[RawItem]:
        fixtures = self._fixtures(query)
        if fixtures is not None:
            return [
                item
                for item in fixtures
                if item.meta.get("sales", self.min_sales) >= self.min_sales
                and item.meta.get("rating", 0) <= self.max_rating
            ][:limit]

        owned = fetcher is None
        fetcher = fetcher or Fetcher()
        items: list[RawItem] = []
        try:
            for endpoint in self.endpoints:
                resp = fetcher.get(endpoint, q=query)
                for listing in _iter_listings(resp.json()):
                    sales = listing.get("sales", 0) or 0
                    rating = listing.get("rating", 5.0) or 5.0
                    if sales < self.min_sales or rating > self.max_rating:
                        continue
                    text = _clean(
                        f"{listing.get('title', '')}. {listing.get('description', '')}"
                    )
                    if len(text) < 40:
                        continue
                    items.append(
                        RawItem(
                            source_kind=self.kind,
                            url=listing.get("url", endpoint),
                            title=listing.get("title"),
                            text=text,
                            meta={
                                "sales": sales,
                                "rating": rating,
                                "price_cents": listing.get("price_cents"),
                            },
                        )
                    )
        finally:
            if owned:
                fetcher.close()
        return items[:limit]


def _iter_reviews(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    for key in ("reviews", "results", "items", "data"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list):
            return [p for p in value if isinstance(p, dict)]
    return []


def _iter_listings(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    for key in ("listings", "products", "results", "items", "data"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list):
            return [p for p in value if isinstance(p, dict)]
    return []


def default_sources(config: dict[str, Any] | None = None) -> list[Source]:
    config = config or {}
    return [
        RedditSource(config.get("subreddits")),
        ForumThreadSource(config.get("forum_urls")),
        ReviewComplaintSource(config.get("review_endpoints")),
        YouTubeCommentSource(
            config.get("video_ids"), api_key=config.get("youtube_api_key")
        ),
        MarketplaceListingSource(config.get("marketplace_endpoints")),
    ]

"""Rate-limit-aware fetching against targets that do not want us there.

Assumptions baked in: the target will rate-limit us, will occasionally serve a
5xx, and may block on User-Agent. So: token-bucket pacing per host, exponential
backoff with jitter honouring `Retry-After`, robots.txt respected by default,
and a fixtures mode so the pipeline is runnable and testable offline.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
import urllib.robotparser
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import settings
from ..ids import fingerprint

log = logging.getLogger("product_factory.sources")


class FetchError(RuntimeError):
    pass


class RobotsDisallowed(FetchError):
    pass


@dataclass
class RawItem:
    """One captured source row, pre-persistence."""

    source_kind: str
    url: str
    text: str
    title: str | None = None
    author: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return fingerprint(self.url, self.text)


class _HostLimiter:
    """Token bucket per host. Shared across threads because a content batch and
    a demand-mining run can be in flight at once."""

    def __init__(self, rate_per_minute: float) -> None:
        self._interval = 60.0 / max(rate_per_minute, 0.1)
        self._next_allowed: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            earliest = self._next_allowed.get(host, 0.0)
            delay = max(0.0, earliest - now)
            self._next_allowed[host] = max(now, earliest) + self._interval
        if delay:
            time.sleep(delay)

    def penalise(self, host: str, seconds: float) -> None:
        with self._lock:
            self._next_allowed[host] = (
                max(self._next_allowed.get(host, 0.0), time.monotonic()) + seconds
            )


class Fetcher:
    def __init__(self) -> None:
        cfg = settings().scrape
        self._cfg = cfg
        self._limiter = _HostLimiter(cfg.requests_per_minute)
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._client = httpx.Client(
            headers={"User-Agent": cfg.user_agent},
            timeout=cfg.timeout_seconds,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _allowed(self, url: str) -> bool:
        if not self._cfg.respect_robots:
            return True
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                resp = self._client.get(f"{origin}/robots.txt")
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser = None  # type: ignore[assignment]
            except httpx.HTTPError:
                parser = None  # type: ignore[assignment]
            self._robots[origin] = parser
        parser = self._robots[origin]
        if parser is None:
            return True  # no robots.txt served == no prohibition
        return parser.can_fetch(self._cfg.user_agent, url)

    def get(self, url: str, **params: Any) -> httpx.Response:
        if not self._allowed(url):
            raise RobotsDisallowed(url)
        host = urlparse(url).netloc
        last_exc: Exception | None = None

        for attempt in range(self._cfg.max_retries):
            self._limiter.wait(host)
            try:
                resp = self._client.get(url, params=params or None)
            except httpx.HTTPError as exc:
                last_exc = exc
                self._backoff(host, attempt)
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    self._limiter.penalise(host, float(retry_after))
                else:
                    self._backoff(host, attempt)
                last_exc = FetchError(f"{resp.status_code} from {url}")
                continue

            if resp.status_code >= 400:
                raise FetchError(f"{resp.status_code} from {url}")
            return resp

        raise FetchError(f"exhausted retries for {url}") from last_exc

    def _backoff(self, host: str, attempt: int) -> None:
        delay = min(60.0, (2**attempt) + random.uniform(0, 1))
        log.info("backing off %.1fs on %s (attempt %s)", delay, host, attempt + 1)
        self._limiter.penalise(host, delay)


class Source:
    """A demand source. Implementations return `RawItem`s; clustering and
    scoring happen in Agent 1, not here."""

    kind: str = "generic"

    def collect(
        self, query: str, *, limit: int = 50, fetcher: Fetcher | None = None
    ) -> list[RawItem]:  # pragma: no cover - interface
        raise NotImplementedError

    # -- fixtures ---------------------------------------------------------- #

    def _fixtures(self, query: str) -> list[RawItem] | None:
        """Offline path. `PF_FIXTURES_DIR/<kind>.json` holds captured rows so a
        run is reproducible without hammering a live target."""
        directory = settings().scrape.fixtures_dir
        if not directory:
            return None
        path = Path(directory) / f"{self.kind}.json"
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get(query) if isinstance(payload, dict) else payload
        if items is None and isinstance(payload, dict):
            items = payload.get("*", [])
        return [
            RawItem(
                source_kind=self.kind,
                url=item["url"],
                text=item["text"],
                title=item.get("title"),
                author=item.get("author"),
                meta=item.get("meta", {}),
            )
            for item in (items or [])
        ]


def dedupe(items: Iterable[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    out: list[RawItem] = []
    for item in items:
        h = item.content_hash
        if h in seen:
            continue
        seen.add(h)
        out.append(item)
    return out

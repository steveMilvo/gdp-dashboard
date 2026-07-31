"""Prefixed, time-sortable identifiers.

Prefixes make foreign keys readable in a log line without a join, and the
millisecond prefix keeps them roughly insertion-ordered so `ORDER BY id` is a
usable proxy for `ORDER BY created_at`.
"""

from __future__ import annotations

import hashlib
import secrets
import time

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32, no I/L/O/U


def _b32(value: int, width: int) -> str:
    out = []
    for _ in range(width):
        out.append(_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def new_id(prefix: str) -> str:
    stamp = _b32(int(time.time() * 1000), 10)
    rand = _b32(secrets.randbits(40), 8)
    return f"{prefix}_{stamp}{rand}"


def fingerprint(*parts: str) -> str:
    """Stable content hash. Used for signal dedup and idempotency keys, so it
    must not depend on dict ordering or wall-clock time."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.strip().lower().encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def token(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)

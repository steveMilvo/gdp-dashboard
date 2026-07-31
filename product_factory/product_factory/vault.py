"""Secret resolution.

Config holds *references* (`env:NAME`, `file:/path`, `awssm:my/secret`), never
values. Everything that needs a credential asks the vault at the point of use.
Two consequences worth keeping: nothing serialisable ever contains a secret,
and `Secret.__repr__` is safe to drop into a traceback.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path


class SecretNotFound(RuntimeError):
    pass


class Secret:
    """A string that refuses to print itself."""

    __slots__ = ("_value", "ref")

    def __init__(self, value: str, ref: str) -> None:
        self._value = value
        self.ref = ref

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Secret ref={self.ref!r} len={len(self._value)}>"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


def _resolve_env(name: str) -> str | None:
    return os.environ.get(name)


def _resolve_file(path: str) -> str | None:
    p = Path(path)
    return p.read_text(encoding="utf-8").strip() if p.is_file() else None


def _resolve_aws_secrets_manager(secret_id: str) -> str | None:
    try:
        import boto3  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SecretNotFound(
            f"awssm:{secret_id} requested but boto3 is not installed"
        ) from exc
    from .config import settings

    client = boto3.client("secretsmanager", region_name=settings().data_region)
    payload = client.get_secret_value(SecretId=secret_id)
    raw = payload.get("SecretString")
    if raw and raw.lstrip().startswith("{"):
        # Convention: a JSON secret with a single key, or a "value" key.
        parsed = json.loads(raw)
        if "value" in parsed:
            return parsed["value"]
        if len(parsed) == 1:
            return next(iter(parsed.values()))
    return raw


_RESOLVERS = {
    "env": _resolve_env,
    "file": _resolve_file,
    "awssm": _resolve_aws_secrets_manager,
}


def resolve(ref: str, *, required: bool = True) -> Secret | None:
    """Resolve `scheme:locator`. A bare string is treated as `env:`."""
    scheme, _, locator = ref.partition(":")
    if not locator:
        scheme, locator = "env", ref
    resolver = _RESOLVERS.get(scheme)
    if resolver is None:
        raise SecretNotFound(f"unknown secret scheme {scheme!r} in ref {ref!r}")
    value = resolver(locator)
    if value:
        return Secret(value, ref)
    if required:
        raise SecretNotFound(f"no secret found at {ref!r}")
    return None


@functools.lru_cache(maxsize=64)
def cached(ref: str) -> Secret:
    secret = resolve(ref, required=True)
    assert secret is not None
    return secret

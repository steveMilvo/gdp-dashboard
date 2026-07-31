"""The single place the factory talks to a model.

Every call goes through `complete_json` or `complete_text`, and every call
writes an `AgentInvocation` row with input, output, model, tokens, cost and
duration. That is what makes per-product unit economics computable from the log
alone — no agent is allowed its own private HTTP call.

Structured output is the default: agents return validated JSON against a schema
rather than prose we then have to parse.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..config import settings
from ..models import AgentInvocation
from ..vault import SecretNotFound, resolve
from . import pricing
from .prompts import Prompt
from .prompts import load as load_prompt

log = logging.getLogger("product_factory.llm")

# Opus 5's safety classifiers can decline a request outright. Server-side
# fallbacks re-run it on a substitute model inside the same call, so a
# false-positive on (say) competitor research doesn't kill a run.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_stub_responder: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
_fallbacks_supported = True


class LLMError(RuntimeError):
    pass


class ModelRefusal(LLMError):
    """`stop_reason == "refusal"` survived the fallback chain."""


@dataclass
class Completion:
    data: Any
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    duration_ms: int = 0
    cost_microcents: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


def set_stub_responder(
    fn: Callable[[str, dict[str, Any]], dict[str, Any]] | None,
) -> None:
    """Install a deterministic responder keyed by prompt name.

    Used by the test suite and by `PF_FIXTURES_DIR` runs so the acceptance
    criteria are exercisable without live credentials or spend.
    """
    global _stub_responder
    _stub_responder = fn


def _client():
    import anthropic

    api_key = None
    try:
        secret = resolve(settings().llm.api_key_ref, required=False)
        api_key = secret.reveal() if secret else None
    except SecretNotFound:  # pragma: no cover - defensive
        api_key = None
    # A bare constructor still resolves an `ant auth login` profile, so we only
    # pass the key when we actually found one.
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def _request_kwargs(
    *,
    system: str,
    user: str,
    schema: dict[str, Any] | None,
    model: str,
    max_tokens: int,
    effort: str,
) -> dict[str, Any]:
    output_config: dict[str, Any] = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
        "thinking": {"type": "adaptive"},
        "output_config": output_config,
    }
    if system:
        # Cached: the system block is the stable prefix across a batch of
        # per-item calls, which is exactly the shape prompt caching rewards.
        kwargs["system"] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    geo = settings().llm.inference_geo
    if geo:
        kwargs["inference_geo"] = geo
    return kwargs


def _invoke_api(kwargs: dict[str, Any]) -> Any:
    global _fallbacks_supported
    import anthropic

    client = _client()
    streaming = kwargs["max_tokens"] > 16000

    def _call(with_fallbacks: bool) -> Any:
        call_kwargs = dict(kwargs)
        if with_fallbacks:
            call_kwargs["betas"] = [_FALLBACK_BETA]
            call_kwargs["extra_body"] = {"fallbacks": "default"}
            api = client.beta.messages
        else:
            api = client.messages
        if streaming:
            with api.stream(**call_kwargs) as stream:
                return stream.get_final_message()
        return api.create(**call_kwargs)

    if _fallbacks_supported:
        try:
            return _call(True)
        except (anthropic.BadRequestError, anthropic.PermissionDeniedError, TypeError) as exc:
            # Org isn't enabled for the beta, or the installed SDK predates it.
            # Degrade once, loudly, and stop paying the failed round trip.
            log.warning("server-side fallbacks unavailable (%s); continuing without", exc)
            _fallbacks_supported = False
    return _call(False)


def _extract_text(message: Any) -> str:
    parts = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


def complete(
    *,
    prompt_name: str,
    variables: dict[str, Any],
    schema: dict[str, Any] | None = None,
    agent: str,
    run_id: str | None = None,
    step_name: str | None = None,
    product_id: str | None = None,
    session: Any = None,
    model: str | None = None,
    max_tokens: int | None = None,
    effort: str | None = None,
    prompt_version: str | None = None,
) -> Completion:
    cfg = settings()
    prompt: Prompt = load_prompt(prompt_name, prompt_version)
    model = model or cfg.llm.model
    max_tokens = max_tokens or cfg.llm.max_tokens
    effort = effort or cfg.llm.effort
    user = prompt.render(**variables)

    started = time.monotonic()
    error: str | None = None
    completion: Completion | None = None

    try:
        if _stub_responder is not None:
            payload = _stub_responder(prompt_name, variables)
            completion = Completion(
                data=payload,
                text=json.dumps(payload),
                model=f"stub:{model}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        else:
            message = _invoke_api(
                _request_kwargs(
                    system=prompt.system,
                    user=user,
                    schema=schema,
                    model=model,
                    max_tokens=max_tokens,
                    effort=effort,
                )
            )
            if getattr(message, "stop_reason", None) == "refusal":
                details = getattr(message, "stop_details", None)
                raise ModelRefusal(
                    f"{prompt_name}: refused"
                    + (f" ({getattr(details, 'category', None)})" if details else "")
                )
            text = _extract_text(message)
            if schema is not None:
                try:
                    data: Any = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise LLMError(
                        f"{prompt_name}: schema was requested but output was not JSON"
                    ) from exc
            else:
                data = text
            usage = message.usage
            completion = Completion(
                data=data,
                text=text,
                model=getattr(message, "model", model),
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0)
                or 0,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            completion.cost_microcents = pricing.cost_microcents(
                completion.model,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                cache_read_tokens=completion.cache_read_tokens,
                cache_write_tokens=completion.cache_write_tokens,
            )
        return completion

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _record(
            session=session,
            run_id=run_id,
            step_name=step_name,
            agent=agent,
            prompt=prompt,
            model=model,
            variables=variables,
            completion=completion,
            product_id=product_id,
            error=error,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


def complete_json(**kwargs: Any) -> Any:
    if kwargs.get("schema") is None:
        raise ValueError("complete_json requires a schema")
    return complete(**kwargs).data


def _truncate(value: Any, limit: int = 8000) -> Any:
    """Invocation rows are for debugging and cost accounting, not archival of
    every scraped byte. Trim the payload rather than bloating the table."""
    text = json.dumps(value, default=str)
    if len(text) <= limit:
        return json.loads(text)
    return {"_truncated": True, "preview": text[:limit]}


def _record(
    *,
    session: Any,
    run_id: str | None,
    step_name: str | None,
    agent: str,
    prompt: Prompt,
    model: str,
    variables: dict[str, Any],
    completion: Completion | None,
    product_id: str | None,
    error: str | None,
    duration_ms: int,
) -> None:
    row = AgentInvocation(
        run_id=run_id,
        step_name=step_name,
        agent=agent,
        prompt_name=prompt.name,
        prompt_version=prompt.version,
        model=completion.model if completion else model,
        input_json=_truncate(variables),
        output_json=_truncate(completion.data) if completion else {},
        input_tokens=completion.input_tokens if completion else 0,
        output_tokens=completion.output_tokens if completion else 0,
        cache_read_tokens=completion.cache_read_tokens if completion else 0,
        cache_write_tokens=completion.cache_write_tokens if completion else 0,
        cost_microcents=completion.cost_microcents if completion else 0,
        duration_ms=duration_ms,
        product_id=product_id,
        error=error,
    )
    try:
        if session is not None:
            session.add(row)
            session.flush()
        else:
            from ..db import session_scope

            with session_scope() as sess:
                sess.add(row)
    except Exception:  # pragma: no cover - logging must never break a run
        log.exception("failed to record agent invocation for %s", agent)

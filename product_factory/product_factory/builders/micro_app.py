"""Micro-app products: spec -> single-purpose web app -> owned hosting.

The generated app is a single stdlib-only Python file against a fixed contract:

    GET  /healthz   -> 200 {"ok": true}
    GET  /          -> 200 HTML, the primary flow
    POST /api/run   -> 200 JSON, the core computation
    (optional) a shared-secret gate on / and /api/run

Fixed contract because it is what makes the smoke test meaningful: the harness
knows exactly what to call and what a working app looks like, rather than
inferring it from whatever the model happened to build.

Stdlib-only is also deliberate. A generated app with a requirements.txt is a
generated app that can fail to install on the buyer-facing host at 3am.

Security note: this executes model-generated Python in a subprocess. It runs on
infrastructure you own, building products you sell — but the static pass below
rejects process spawning, filesystem writes outside the app directory, and
arbitrary imports before anything is executed.
"""

from __future__ import annotations

import ast
import json
import logging
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..ids import token
from ..llm import client as llm

log = logging.getLogger("product_factory.builders.microapp")

SPEC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "one_liner": {"type": "string"},
        "primary_flow": {
            "type": "string",
            "description": "The single thing a buyer does with this app, in one "
            "sentence. If it needs two sentences it is two apps.",
        },
        "inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["text", "number", "textarea", "select"],
                    },
                    "options": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["key", "label", "type", "options"],
                "additionalProperties": False,
            },
        },
        "output_description": {"type": "string"},
        "requires_auth": {"type": "boolean"},
    },
    "required": [
        "name",
        "one_liner",
        "primary_flow",
        "inputs",
        "output_description",
        "requires_auth",
    ],
    "additionalProperties": False,
}

CODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "compute_source": {
            "type": "string",
            "description": "Body of `def compute(payload: dict) -> dict:` including "
            "the def line. Python standard library only.",
        },
        "notes": {"type": "string"},
    },
    "required": ["compute_source", "notes"],
    "additionalProperties": False,
}

# The generated compute function may use these and nothing else.
_ALLOWED_IMPORTS = {
    "math",
    "json",
    "re",
    "datetime",
    "statistics",
    "decimal",
    "fractions",
    "itertools",
    "functools",
    "collections",
    "textwrap",
    "random",
    "string",
    "typing",
    "dataclasses",
    "enum",
    "calendar",
    "urllib.parse",
    "html",
    "base64",
    "hashlib",
    "uuid",
}
_FORBIDDEN_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "input",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "breakpoint",
}


@dataclass
class MicroAppResult:
    directory: Path
    entrypoint: Path
    spec: dict[str, Any]
    auth_token: str | None
    static_report: str


class UnsafeGeneratedCode(RuntimeError):
    pass


def build(
    *,
    output_dir: Path,
    slug: str,
    promise: str,
    target_buyer: str,
    signals: list[dict[str, str]],
    session: Any = None,
    run_id: str | None = None,
    step_name: str | None = None,
    product_id: str | None = None,
) -> MicroAppResult:
    app_dir = output_dir / slug
    app_dir.mkdir(parents=True, exist_ok=True)

    spec = llm.complete_json(
        prompt_name="micro_app_spec",
        variables={
            "promise": promise,
            "target_buyer": target_buyer,
            "signals": "\n".join(
                f"- {s['normalised']} (verbatim: \"{s['quote']}\")" for s in signals
            ),
        },
        schema=SPEC_SCHEMA,
        agent="artifact_builder.micro_app",
        run_id=run_id,
        step_name=step_name,
        product_id=product_id,
        session=session,
    )

    code = llm.complete_json(
        prompt_name="micro_app_compute",
        variables={
            "name": spec["name"],
            "primary_flow": spec["primary_flow"],
            "output_description": spec["output_description"],
            "inputs": "\n".join(
                f"- {i['key']} ({i['type']}): {i['label']}" for i in spec["inputs"]
            ),
            "allowed_imports": ", ".join(sorted(_ALLOWED_IMPORTS)),
        },
        schema=CODE_SCHEMA,
        agent="artifact_builder.micro_app",
        run_id=run_id,
        step_name=step_name,
        product_id=product_id,
        session=session,
    )

    report = static_check(code["compute_source"])
    auth_token = token(18) if spec.get("requires_auth") else None

    entrypoint = app_dir / "app.py"
    entrypoint.write_text(
        _render_app(spec, code["compute_source"], auth_token), encoding="utf-8"
    )
    (app_dir / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    if auth_token:
        (app_dir / "ACCESS.txt").write_text(
            "Access token for this app (share with the buyer, keep out of git):\n"
            f"{auth_token}\n",
            encoding="utf-8",
        )

    return MicroAppResult(
        directory=app_dir,
        entrypoint=entrypoint,
        spec=spec,
        auth_token=auth_token,
        static_report=report,
    )


def static_check(source: str) -> str:
    """Reject dangerous constructs before anything is written to disk."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise UnsafeGeneratedCode(f"generated compute does not parse: {exc}") from exc

    has_compute = any(
        isinstance(node, ast.FunctionDef) and node.name == "compute"
        for node in tree.body
    )
    if not has_compute:
        raise UnsafeGeneratedCode("generated source defines no `compute` function")

    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _ALLOWED_IMPORTS:
                    problems.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in _ALLOWED_IMPORTS:
                problems.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            problems.append(f"use of {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            problems.append(f"dunder attribute access .{node.attr}")

    if problems:
        raise UnsafeGeneratedCode(
            "generated compute uses disallowed constructs: " + ", ".join(sorted(set(problems)))
        )
    return f"{len(tree.body)} top-level nodes, imports within allowlist"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


_APP_TEMPLATE = '''"""{name} — generated by Product Factory.

{one_liner}

Run: PORT=8080 python app.py
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Parsed at runtime rather than inlined as a Python literal: JSON's `false`,
# `true` and `null` are not Python names, and a spec with a boolean field would
# otherwise produce an app that dies on import.
SPEC = json.loads(r"""{spec_json}""")
AUTH_TOKEN = {auth_token!r}


{compute_source}


def _authorised(handler):
    if not AUTH_TOKEN:
        return True
    header = handler.headers.get("Authorization", "")
    if header == "Bearer " + AUTH_TOKEN:
        return True
    from urllib.parse import parse_qs, urlparse

    query = parse_qs(urlparse(handler.path).query)
    return query.get("token", [None])[0] == AUTH_TOKEN


def _field_html(field):
    label = "<label for='{{k}}'>{{l}}</label>".format(k=field["key"], l=field["label"])
    if field["type"] == "textarea":
        control = "<textarea id='{{k}}' name='{{k}}' rows='4'></textarea>".format(k=field["key"])
    elif field["type"] == "select":
        options = "".join(
            "<option value='{{o}}'>{{o}}</option>".format(o=o) for o in field.get("options", [])
        )
        control = "<select id='{{k}}' name='{{k}}'>{{o}}</select>".format(k=field["key"], o=options)
    else:
        input_type = "number" if field["type"] == "number" else "text"
        control = "<input id='{{k}}' name='{{k}}' type='{{t}}'>".format(
            k=field["key"], t=input_type
        )
    return "<div class='field'>" + label + control + "</div>"


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
 :root {{ color-scheme: light dark; }}
 body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 44rem; margin: 3rem auto;
        padding: 0 1.25rem; }}
 h1 {{ font-size: 1.6rem; margin-bottom: .25rem; }}
 p.lede {{ color: #666; margin-top: 0; }}
 .field {{ display: grid; gap: .35rem; margin-bottom: 1rem; }}
 label {{ font-weight: 600; font-size: .9rem; }}
 input, select, textarea {{ padding: .55rem; font: inherit; border: 1px solid #999;
        border-radius: 6px; background: transparent; color: inherit; }}
 button {{ padding: .65rem 1.25rem; font: inherit; font-weight: 600; border: 0;
        border-radius: 6px; background: #12263a; color: #fff; cursor: pointer; }}
 pre {{ background: rgba(127,127,127,.12); padding: 1rem; border-radius: 8px;
        white-space: pre-wrap; word-break: break-word; }}
</style></head><body>
<h1>__TITLE__</h1><p class="lede">__LEDE__</p>
<form id="f">__FIELDS__<button type="submit">Run</button></form>
<pre id="out" hidden></pre>
<script>
document.getElementById('f').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  const out = document.getElementById('out');
  out.hidden = false; out.textContent = 'Working...';
  const res = await fetch('/api/run' + window.location.search, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(payload)
  }});
  const data = await res.json();
  out.textContent = JSON.stringify(data, null, 2);
}});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, body, content_type="application/json"):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/healthz":
            return self._send(200, json.dumps({{"ok": True, "app": SPEC["name"]}}))
        if path != "/":
            return self._send(404, json.dumps({{"error": "not found"}}))
        if not _authorised(self):
            return self._send(401, json.dumps({{"error": "token required"}}))
        html = (
            PAGE.replace("__TITLE__", SPEC["name"])
            .replace("__LEDE__", SPEC["one_liner"])
            .replace("__FIELDS__", "".join(_field_html(f) for f in SPEC["inputs"]))
        )
        return self._send(200, html, "text/html")

    def do_POST(self):
        if self.path.split("?")[0] != "/api/run":
            return self._send(404, json.dumps({{"error": "not found"}}))
        if not _authorised(self):
            return self._send(401, json.dumps({{"error": "token required"}}))
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{{}}"
        try:
            payload = json.loads(raw or b"{{}}")
        except ValueError:
            return self._send(400, json.dumps({{"error": "invalid JSON"}}))
        try:
            result = compute(payload)
        except Exception as exc:
            return self._send(400, json.dumps({{"error": str(exc)}}))
        return self._send(200, json.dumps({{"ok": True, "result": result}}, default=str))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
'''


def _render_app(spec: dict[str, Any], compute_source: str, auth_token: str | None) -> str:
    # `/` must render without a token during the smoke test, so an auth-gated
    # app is smoke-tested against /healthz plus a token-bearing request.
    return _APP_TEMPLATE.format(
        name=spec["name"],
        one_liner=spec["one_liner"],
        spec_json=json.dumps(spec, indent=4),
        auth_token=auth_token,
        compute_source=compute_source.strip(),
    )

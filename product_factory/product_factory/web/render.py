"""One page shell for every surface.

Inlined CSS rather than a static mount: these pages are served from a single
process that may be behind a CDN we don't control, and one fewer request on a
landing page is one fewer thing to be slow.
"""

from __future__ import annotations

_CSS = """
:root { color-scheme: light dark; --ink:#12263a; --accent:#c05621; --muted:#6b7280; }
@media (prefers-color-scheme: dark) { :root { --ink:#e8e6e3; --muted:#9ca3af; } }
* { box-sizing: border-box; }
body { font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui,
       sans-serif; max-width: 48rem; margin: 0 auto; padding: 3rem 1.25rem 6rem;
       color: var(--ink); }
h1 { font-size: clamp(1.6rem, 4vw, 2.3rem); line-height: 1.2; margin: 0 0 .75rem; }
h2 { font-size: 1.3rem; margin-top: 2.5rem; border-bottom: 1px solid rgba(127,127,127,.25);
     padding-bottom: .35rem; }
h3 { font-size: 1.05rem; margin-bottom: .35rem; }
p.lede { font-size: 1.15rem; color: var(--muted); }
p.fine { font-size: .85rem; color: var(--muted); }
dl dt { font-weight: 650; margin-top: 1rem; }
dl dd { margin: .25rem 0 0; color: var(--muted); }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85em;
       background: rgba(127,127,127,.14); padding: .1rem .35rem; border-radius: 4px; }
pre { background: rgba(127,127,127,.12); padding: 1rem; border-radius: 8px;
      overflow-x: auto; font-size: .8rem; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .9rem;
        display: block; overflow-x: auto; }
th, td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid rgba(127,127,127,.2); }
th { font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
form { display: grid; gap: .6rem; max-width: 26rem; margin: 1.5rem 0; }
label { font-weight: 600; font-size: .9rem; }
input, select { padding: .65rem; font: inherit; border: 1px solid rgba(127,127,127,.5);
        border-radius: 6px; background: transparent; color: inherit; }
button, .button { display: inline-block; padding: .7rem 1.4rem; font: inherit;
        font-weight: 650; border: 0; border-radius: 6px; background: var(--accent);
        color: #fff; cursor: pointer; text-decoration: none; }
button[disabled] { opacity: .5; cursor: not-allowed; }
.price-tag { font-size: 1.5rem; font-weight: 700; }
article { border: 1px solid rgba(127,127,127,.3); border-radius: 10px; padding: 1rem 1.2rem;
        margin-bottom: 1rem; }
.pill { font-size: .75rem; padding: .15rem .5rem; border-radius: 999px;
        background: rgba(127,127,127,.2); }
.pill.succeeded { background: #10b98133; } .pill.failed { background: #ef444433; }
.pill.awaiting_gate { background: #f59e0b33; } .pill.running { background: #3b82f633; }
footer { margin-top: 4rem; font-size: .8rem; color: var(--muted); }
"""


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en-AU"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head><body>
{body}
<footer>Product Factory · Australian entity · data stored onshore</footer>
</body></html>"""


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

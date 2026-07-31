"""Deterministic quality gates.

Hard rule from the spec: no artifact ships without a mechanical pass
appropriate to its type. "Mechanical" is doing work in that sentence — these
checks are code, not another model call. A model grading its own output is not
verification.

Each check returns `(name, passed, detail)`. `run_checks` persists them against
the artifact version and flips `quality_passed` only if every check passed.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx

from ..models import ArtifactVersion, QualityCheck

log = logging.getLogger("product_factory.quality")

CheckResult = tuple[str, bool, str]

_URL = re.compile(r"https?://[^\s<>\"')]+")
_PLACEHOLDERS = re.compile(
    r"\b(lorem ipsum|todo|tbd|fixme|placeholder|xxx|\[insert[^\]]*\]|"
    r"as an ai language model)\b",
    re.I,
)
_DOUBLE_SPACE_SENTENCE = re.compile(r"[a-z]{2,}\s{2,}[a-z]{2,}")
_REPEATED_WORD = re.compile(r"\b(\w{4,})\s+\1\b", re.I)


@dataclass
class QualityReport:
    checks: list[CheckResult]

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c[1]]


# --------------------------------------------------------------------------- #
# Shared checks
# --------------------------------------------------------------------------- #


def check_no_placeholders(text: str) -> CheckResult:
    hits = sorted({m.group(0).lower() for m in _PLACEHOLDERS.finditer(text)})
    return (
        "no_placeholders",
        not hits,
        "clean" if not hits else f"found placeholder text: {hits}",
    )


def check_prose_hygiene(text: str, *, min_words: int = 400) -> CheckResult:
    """Cheap, deterministic stand-in for a grammar pass: word count floor,
    no doubled words, no doubled spacing mid-sentence. Catches the failure
    modes generated prose actually has."""
    words = len(text.split())
    problems: list[str] = []
    if words < min_words:
        problems.append(f"only {words} words (floor {min_words})")
    doubled = {m.group(1).lower() for m in _REPEATED_WORD.finditer(text)}
    if doubled:
        problems.append(f"repeated words: {sorted(doubled)[:5]}")
    if _DOUBLE_SPACE_SENTENCE.search(text):
        problems.append("irregular intra-sentence spacing")
    return (
        "prose_hygiene",
        not problems,
        "ok" if not problems else "; ".join(problems),
    )


def check_links(text: str, *, timeout: float = 8.0, max_links: int = 25) -> CheckResult:
    urls = sorted(set(_URL.findall(text)))[:max_links]
    if not urls:
        return ("link_check", True, "no external links")
    broken: list[str] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = client.head(url)
                if resp.status_code >= 400:
                    resp = client.get(url)
                if resp.status_code >= 400:
                    broken.append(f"{url} -> {resp.status_code}")
            except httpx.HTTPError as exc:
                broken.append(f"{url} -> {type(exc).__name__}")
    return (
        "link_check",
        not broken,
        f"{len(urls)} links ok" if not broken else f"broken: {broken}",
    )


def check_file_exists(path: Path, *, min_bytes: int = 1024) -> CheckResult:
    if not path.is_file():
        return ("file_present", False, f"missing {path}")
    size = path.stat().st_size
    return (
        "file_present",
        size >= min_bytes,
        f"{size} bytes" if size >= min_bytes else f"only {size} bytes",
    )


# --------------------------------------------------------------------------- #
# Format-specific
# --------------------------------------------------------------------------- #


def check_pdf(path: Path, *, min_pages: int = 5) -> CheckResult:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = len(reader.pages)
        extracted = (reader.pages[0].extract_text() or "").strip()
    except Exception as exc:  # noqa: BLE001
        return ("pdf_readable", False, f"{type(exc).__name__}: {exc}")
    if pages < min_pages:
        return ("pdf_readable", False, f"only {pages} pages (floor {min_pages})")
    if not extracted:
        return ("pdf_readable", False, "first page has no extractable text")
    return ("pdf_readable", True, f"{pages} pages, text extractable")


def check_template_load(paths: Iterable[Path]) -> CheckResult:
    """Every template file must parse with a standard reader. A template pack
    that a buyer cannot open is worse than no product."""
    problems: list[str] = []
    checked = 0
    for path in paths:
        checked += 1
        try:
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".csv":
                with path.open(newline="", encoding="utf-8") as fh:
                    rows = list(csv.reader(fh))
                if len(rows) < 1 or not rows[0]:
                    problems.append(f"{path.name}: no header row")
            elif path.suffix in {".md", ".txt"}:
                if not path.read_text(encoding="utf-8").strip():
                    problems.append(f"{path.name}: empty")
            else:
                if path.stat().st_size == 0:
                    problems.append(f"{path.name}: empty")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path.name}: {type(exc).__name__}: {exc}")
    if checked == 0:
        return ("template_load", False, "no template files produced")
    return (
        "template_load",
        not problems,
        f"{checked} files parsed" if not problems else "; ".join(problems),
    )


def check_schema_parity(populated: Path, blank: Path) -> CheckResult:
    """The blank version must have the same shape as the worked example, or
    the usage guide describes something the buyer doesn't have."""
    try:
        if populated.suffix == ".json":
            a = json.loads(populated.read_text(encoding="utf-8"))
            b = json.loads(blank.read_text(encoding="utf-8"))
            keys_a = set(a[0]) if isinstance(a, list) and a else set(a or {})
            keys_b = set(b[0]) if isinstance(b, list) and b else set(b or {})
        else:
            with populated.open(newline="", encoding="utf-8") as fh:
                keys_a = set(next(csv.reader(fh), []))
            with blank.open(newline="", encoding="utf-8") as fh:
                keys_b = set(next(csv.reader(fh), []))
    except Exception as exc:  # noqa: BLE001
        return ("schema_parity", False, f"{type(exc).__name__}: {exc}")
    missing = keys_a ^ keys_b
    return (
        "schema_parity",
        not missing,
        "identical schema" if not missing else f"field mismatch: {sorted(missing)}",
    )


def check_app_smoke(
    app_dir: Path, *, port: int, primary_path: str = "/", timeout: float = 25.0
) -> CheckResult:
    """Boot the generated app, hit the primary flow, shut it down.

    A generated web app that has never been started is an untested claim. This
    starts a real process and makes a real request against it.
    """
    entry = app_dir / "app.py"
    if not entry.is_file():
        return ("app_smoke", False, "no app.py in the generated app")

    proc = subprocess.Popen(  # noqa: S603 - our own generated entrypoint
        [sys.executable, str(entry)],
        cwd=str(app_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={"PORT": str(port), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + timeout
    try:
        last_error = "did not start"
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out = (proc.stdout.read() if proc.stdout else "") or ""
                return ("app_smoke", False, f"process exited: {out[-500:]}")
            try:
                with httpx.Client(timeout=3.0) as client:
                    health = client.get(f"{base}/healthz")
                    if health.status_code != 200:
                        last_error = f"/healthz -> {health.status_code}"
                        time.sleep(0.4)
                        continue
                    primary = client.get(f"{base}{primary_path}")
                    if primary.status_code != 200:
                        return (
                            "app_smoke",
                            False,
                            f"{primary_path} -> {primary.status_code}",
                        )
                    return (
                        "app_smoke",
                        True,
                        f"healthz ok, {primary_path} returned 200",
                    )
            except httpx.HTTPError as exc:
                last_error = type(exc).__name__
                time.sleep(0.4)
        return ("app_smoke", False, f"timed out after {timeout}s ({last_error})")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()


def check_course_structure(
    modules: list[dict], *, min_modules: int = 3, min_lessons: int = 6
) -> CheckResult:
    lessons = sum(len(m.get("lessons", [])) for m in modules)
    problems = []
    if len(modules) < min_modules:
        problems.append(f"{len(modules)} modules (floor {min_modules})")
    if lessons < min_lessons:
        problems.append(f"{lessons} lessons (floor {min_lessons})")
    empty = [
        lesson.get("title", "?")
        for module in modules
        for lesson in module.get("lessons", [])
        if len((lesson.get("script") or "").split()) < 120
    ]
    if empty:
        problems.append(f"thin scripts: {empty[:3]}")
    return (
        "course_structure",
        not problems,
        f"{len(modules)} modules / {lessons} lessons"
        if not problems
        else "; ".join(problems),
    )


# --------------------------------------------------------------------------- #


def run_checks(
    session,
    artifact: ArtifactVersion,
    checks: Iterable[Callable[[], CheckResult] | CheckResult],
) -> QualityReport:
    results: list[CheckResult] = []
    for check in checks:
        try:
            result = check() if callable(check) else check
        except Exception as exc:  # noqa: BLE001
            result = ("unknown_check", False, f"{type(exc).__name__}: {exc}")
        results.append(result)
        session.add(
            QualityCheck(
                artifact_version_id=artifact.id,
                name=result[0],
                passed=result[1],
                detail=result[2],
            )
        )
    report = QualityReport(results)
    artifact.quality_passed = report.passed
    session.flush()
    if not report.passed:
        log.warning(
            "artifact %s failed quality: %s", artifact.id, report.failures()
        )
    return report

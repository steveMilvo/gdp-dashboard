"""Agent 4 — Artifact Builder.

Dispatches to the format-specific generator, then runs the deterministic
quality pass for that format. `quality_passed` is set by `run_checks`, and
Agent 5 refuses to list an artifact that doesn't carry it — so the hard rule
("no artifact ships without a mechanical pass") is enforced by the storefront,
not by convention.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..builders import course as course_builder
from ..builders import deploy as deployer
from ..builders import document as document_builder
from ..builders import micro_app as app_builder
from ..builders import quality
from ..builders import template_pack as template_builder
from ..config import settings
from ..models import (
    ArtifactVersion,
    ClusterMember,
    Objection,
    OfferCandidate,
    PainSignal,
    Product,
    ProductFormat,
    ValidationRun,
)

log = logging.getLogger("product_factory.agent4")


@dataclass
class BuildResult:
    product_id: str
    artifact_version_id: str
    quality_passed: bool
    failures: list[tuple[str, bool, str]]
    url: str | None = None


class QualityGateFailed(RuntimeError):
    def __init__(self, failures: list[tuple[str, bool, str]]) -> None:
        super().__init__("; ".join(f"{n}: {d}" for n, _, d in failures))
        self.failures = failures


def build_product(
    session: Session,
    *,
    offer_candidate_id: str,
    run_id: str | None = None,
    step_name: str | None = None,
    strict: bool = True,
) -> BuildResult:
    candidate = session.get(OfferCandidate, offer_candidate_id)
    if candidate is None:
        raise KeyError(f"no such offer candidate {offer_candidate_id!r}")

    signals = _signals_for(session, candidate)
    objections = _objections_for(session, candidate)
    product = _ensure_product(session, candidate)
    version = _next_version(session, product.id)
    cfg = settings()

    kind = candidate.format
    artifact = ArtifactVersion(
        product_id=product.id, version=version, kind=kind
    )
    session.add(artifact)
    session.flush()

    common = {
        "slug": f"{product.slug}-v{version}",
        "promise": candidate.promise,
        "target_buyer": candidate.target_buyer,
        "signals": signals,
        "session": session,
        "run_id": run_id,
        "step_name": step_name,
        "product_id": product.id,
    }

    if kind in {ProductFormat.EBOOK.value, ProductFormat.NOTION_SYSTEM.value}:
        checks, url = _build_document(
            artifact, cfg.artifacts_dir, objections=objections, **common
        )
    elif kind == ProductFormat.TEMPLATE_PACK.value:
        checks, url = _build_templates(artifact, cfg.artifacts_dir, **common)
    elif kind == ProductFormat.MICRO_APP.value:
        checks, url = _build_micro_app(artifact, cfg.apps_dir, **common)
    elif kind == ProductFormat.MINI_COURSE.value:
        checks, url = _build_course(artifact, cfg.artifacts_dir, **common)
    else:
        raise ValueError(f"no builder for format {kind!r}")

    report = quality.run_checks(session, artifact, checks)
    artifact.url = url
    session.flush()

    if strict and not report.passed:
        raise QualityGateFailed(report.failures())

    return BuildResult(
        product_id=product.id,
        artifact_version_id=artifact.id,
        quality_passed=report.passed,
        failures=report.failures(),
        url=url,
    )


# --------------------------------------------------------------------------- #
# Format dispatch
# --------------------------------------------------------------------------- #


def _build_document(
    artifact: ArtifactVersion,
    output_dir: Path,
    *,
    objections: list[str],
    **kwargs: Any,
) -> tuple[list[Any], str | None]:
    result = document_builder.build(
        output_dir=output_dir, objections=objections, **kwargs
    )
    artifact.path = str(result.pdf_path)
    artifact.cover_path = str(result.cover_path)
    artifact.bytes = result.pdf_path.stat().st_size
    artifact.checksum = _checksum(result.pdf_path)
    artifact.meta = {
        "title": result.title,
        "sections": [s["heading"] for s in result.sections],
    }
    return (
        [
            lambda: quality.check_file_exists(result.pdf_path, min_bytes=8_000),
            lambda: quality.check_pdf(result.pdf_path),
            lambda: quality.check_file_exists(result.cover_path, min_bytes=1_000),
            lambda: quality.check_no_placeholders(result.full_text),
            lambda: quality.check_prose_hygiene(result.full_text, min_words=2500),
            lambda: quality.check_links(result.full_text),
        ],
        None,
    )


def _build_templates(
    artifact: ArtifactVersion, output_dir: Path, **kwargs: Any
) -> tuple[list[Any], str | None]:
    result = template_builder.build(output_dir=output_dir, **kwargs)
    archive = _zip(result.directory)
    artifact.path = str(archive)
    artifact.bytes = archive.stat().st_size
    artifact.checksum = _checksum(archive)
    artifact.meta = {"files": [str(p.relative_to(result.directory)) for p in result.files]}
    checks: list[Any] = [
        lambda: quality.check_template_load(result.files),
        lambda: quality.check_no_placeholders(result.guide_text),
        lambda: quality.check_prose_hygiene(result.guide_text, min_words=600),
        lambda: quality.check_file_exists(archive, min_bytes=1_000),
    ]
    checks += [
        (lambda p=pair: quality.check_schema_parity(p[0], p[1])) for pair in result.pairs
    ]
    return checks, None


def _build_micro_app(
    artifact: ArtifactVersion, apps_dir: Path, **kwargs: Any
) -> tuple[list[Any], str | None]:
    result = app_builder.build(output_dir=apps_dir, **kwargs)
    slug = kwargs["slug"]

    # Smoke-test on a throwaway port before the app is ever exposed.
    smoke = quality.check_app_smoke(
        result.directory,
        port=app_builder.free_port(),
        primary_path="/healthz" if result.auth_token else "/",
    )
    url: str | None = None
    if smoke[1]:
        deployment = deployer.deploy(
            slug=slug, app_dir=result.directory, auth_token=result.auth_token
        )
        url = deployment.url

    artifact.path = str(result.entrypoint)
    artifact.bytes = result.entrypoint.stat().st_size
    artifact.checksum = _checksum(result.entrypoint)
    artifact.meta = {
        "spec": result.spec,
        "static_check": result.static_report,
        "requires_auth": bool(result.auth_token),
    }
    return (
        [
            smoke,
            lambda: quality.check_file_exists(result.entrypoint, min_bytes=500),
            ("static_analysis", True, result.static_report),
        ],
        url,
    )


def _build_course(
    artifact: ArtifactVersion, output_dir: Path, **kwargs: Any
) -> tuple[list[Any], str | None]:
    result = course_builder.build(output_dir=output_dir, **kwargs)
    archive = _zip(result.directory)
    artifact.path = str(archive)
    artifact.bytes = archive.stat().st_size
    artifact.checksum = _checksum(archive)
    artifact.meta = {
        "title": result.title,
        "modules": [m["title"] for m in result.modules],
    }
    checks: list[Any] = [
        lambda: quality.check_course_structure(result.modules),
        lambda: quality.check_no_placeholders(result.full_text),
        lambda: quality.check_prose_hygiene(result.full_text, min_words=2000),
        lambda: quality.check_file_exists(archive, min_bytes=2_000),
    ]
    checks += [
        (lambda p=path: quality.check_pdf(p, min_pages=2)) for path in result.deck_paths
    ]
    return checks, None


# --------------------------------------------------------------------------- #


def _ensure_product(session: Session, candidate: OfferCandidate) -> Product:
    product = session.scalar(
        select(Product).where(Product.offer_candidate_id == candidate.id)
    )
    if product is not None:
        return product
    slug = _slugify(candidate.promise)[:60] or "product"
    if session.scalar(select(Product).where(Product.slug == slug)) is not None:
        slug = f"{slug}-{candidate.id[-6:]}"
    product = Product(
        offer_candidate_id=candidate.id,
        name=candidate.promise[:180],
        slug=slug,
        format=candidate.format,
        spec={
            "promise": candidate.promise,
            "target_buyer": candidate.target_buyer,
            "price_cents": candidate.price_cents,
        },
    )
    session.add(product)
    session.flush()
    return product


def _next_version(session: Session, product_id: str) -> int:
    current = session.scalar(
        select(func.max(ArtifactVersion.version)).where(
            ArtifactVersion.product_id == product_id
        )
    )
    return (current or 0) + 1


def _signals_for(session: Session, candidate: OfferCandidate) -> list[dict[str, str]]:
    rows = session.scalars(
        select(PainSignal)
        .join(ClusterMember, ClusterMember.pain_signal_id == PainSignal.id)
        .where(ClusterMember.cluster_id == candidate.cluster_id)
        .order_by(PainSignal.score.desc())
    ).all()
    return [
        {"id": s.id, "quote": s.quote, "normalised": s.normalised} for s in rows
    ]


def _objections_for(session: Session, candidate: OfferCandidate) -> list[str]:
    rows = session.scalars(
        select(Objection)
        .join(ValidationRun, ValidationRun.id == Objection.validation_run_id)
        .where(ValidationRun.offer_candidate_id == candidate.id)
    ).all()
    return [row.text for row in rows]


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip(directory: Path) -> Path:
    import shutil

    archive = directory.parent / f"{directory.name}.zip"
    if archive.exists():
        archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=directory)
    return archive


def _slugify(name: str) -> str:
    return "-".join(
        part
        for part in "".join(c.lower() if c.isalnum() else " " for c in name).split()
    )

"""Main FastAPI application for TrustShop AI."""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import tldextract
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.brand_identity import brand_identity_scorer
from app.agents.domain import domain_scorer
from app.agents.message import message_scorer
from app.agents.number import number_scorer
from app.agents.payment import payment_scorer
from app.decision import calculate_decision
from app.errors import setup_exception_handlers
from app.explain import generate_explanation
from app.extraction import extract_check_context, normalize_phone
from app.registry import (
    get_all_brands,
    get_brand_by_slug,
    get_report_stats,
    get_session_factory,
    init_db,
    record_report,
)
from app.schemas import (
    BrandMatchResult,
    BrandResponse,
    BrandSourceResponse,
    ChannelMatch,
    CheckRequest,
    CheckResponse,
    ReportCreateRequest,
    ReportResponse,
    ScorerResultItem,
)
from scripts.seed_registry import seed_registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def get_db():
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB and ensure tables exist
    init_db()
    # Auto-seed if empty
    session_factory = get_session_factory()
    with session_factory() as session:
        brands = get_all_brands(session)
        if not brands:
            yaml_path = PROJECT_ROOT / "registry" / "brands.yaml"
            if yaml_path.exists():
                seed_registry(yaml_path)
    yield


app = FastAPI(
    title="TrustShop AI",
    description="Check WhatsApp sellers, phone numbers, links, and payment IDs before you pay.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Attach RFC 9457 error handlers
setup_exception_handlers(app)


@app.get("/healthz", tags=["System"])
async def healthz():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/readyz", tags=["System"])
async def readyz(db: Annotated[Session, Depends(get_db)]):
    """Readiness probe checking database availability."""
    try:
        get_all_brands(db)
        return {"status": "ready"}
    except (SQLAlchemyError, Exception) as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {e}",
        )


@app.get("/v1/brands", response_model=list[BrandResponse], tags=["Brands"])
async def list_brands(db: Annotated[Session, Depends(get_db)]):
    """List all official brands recorded in the registry."""
    brands = get_all_brands(db)
    return [
        BrandResponse(
            slug=b.slug,
            name=b.name,
            official_domains=[d.domain for d in b.domains],
            official_phones=[p.phone_e164 for p in b.phones],
            payment_policy=b.payment_policy,
            sources=[
                BrandSourceResponse(url=s.url, verified_on=s.verified_on)
                for s in b.sources
            ],
        )
        for b in brands
    ]


@app.get("/v1/brands/{slug}", response_model=BrandResponse, tags=["Brands"])
async def get_brand(slug: str, db: Annotated[Session, Depends(get_db)]):
    """Get official channels and sources for a single brand."""
    brand = get_brand_by_slug(db, slug)
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand with slug '{slug}' not found in registry.",
        )
    return BrandResponse(
        slug=brand.slug,
        name=brand.name,
        official_domains=[d.domain for d in brand.domains],
        official_phones=[p.phone_e164 for p in brand.phones],
        payment_policy=brand.payment_policy,
        sources=[
            BrandSourceResponse(url=s.url, verified_on=s.verified_on)
            for s in brand.sources
        ],
    )


@app.post("/v1/checks", response_model=CheckResponse, tags=["Checks"])
async def create_check(payload: CheckRequest, db: Annotated[Session, Depends(get_db)]):
    """Check a seller's phone number, chat text, link, and payment details."""
    start_time = time.perf_counter()
    check_id = f"c_{uuid.uuid4().hex[:8]}"

    # 1. Fetch registry brands for brand matching
    db_brands = get_all_brands(db)
    registry_list = [b.to_dict() for b in db_brands]

    # 2. Extract and normalize inputs
    payment_dict = payload.payment.model_dump() if payload.payment else None
    ctx = extract_check_context(
        phone_number=payload.phone_number,
        message_text=payload.message_text,
        urls=payload.urls,
        claimed_brand=payload.claimed_brand,
        payment=payment_dict,
        language=payload.language,
        registry_brands=registry_list,
    )

    # 3. Execute all 5 scorers in parallel
    brand_res, pay_res, msg_res, dom_res, num_res = await asyncio.gather(
        brand_identity_scorer(ctx),
        payment_scorer(ctx),
        message_scorer(ctx),
        domain_scorer(ctx),
        number_scorer(ctx, db_session=db),
    )

    raw_scores: dict[str, dict[str, Any]] = {
        "brand_identity": brand_res,
        "payment": pay_res,
        "message": msg_res,
        "domain": dom_res,
        "number": num_res,
    }

    # 4. Compute verdict through decision layer
    decision = calculate_decision(ctx, raw_scores)

    # 5. Generate human-readable reasons, summary, and actionable advice
    explanation = generate_explanation(ctx, decision.verdict, decision.reason_codes)

    # 6. Format brand match metadata
    brand_match_result: BrandMatchResult | None = None
    if ctx.brand:
        ev = brand_res.get("evidence", {})
        brand_match_result = BrandMatchResult(
            claimed=ctx.brand.get("claimed"),
            in_registry=bool(ctx.brand.get("in_registry", False)),
            registry_verified_on=ev.get("latest_verified_on"),
            match=ChannelMatch(
                phone=ev.get("phone_matched") if ev.get("phone_checked") else None,
                domain=ev.get("domain_matched") if ev.get("domain_checked") else None,
                payment=None,
            ),
        )

    # 7. Convert scores to response schema
    formatted_scores = {
        k: ScorerResultItem(
            status=v.get("status", "not_applicable"),
            risk=v.get("risk"),
            reasons=v.get("reasons", []),
            flags=v.get("flags", []),
            evidence=v.get("evidence", {}),
        )
        for k, v in raw_scores.items()
    }

    latency = round((time.perf_counter() - start_time) * 1000, 2)

    return CheckResponse(
        check_id=check_id,
        verdict=decision.verdict,  # type: ignore
        risk_score=decision.risk_score,
        brand=brand_match_result,
        scores=formatted_scores,
        reason_codes=decision.reason_codes,
        reasons=explanation["reasons"],
        summary=explanation["summary"],
        advice=explanation["advice"],
        degraded=decision.degraded,
        latency_ms=latency,
    )


@app.post(
    "/v1/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Reports"],
)
async def create_report(
    payload: ReportCreateRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Submit a community report against a suspicious phone number, website link, or UPI ID."""
    norm_id = payload.identifier.strip()
    if payload.identifier_type == "phone":
        p_res = normalize_phone(norm_id)
        if p_res.get("valid") and p_res.get("e164"):
            norm_id = p_res["e164"]
    elif payload.identifier_type == "domain":
        ext = tldextract.extract(norm_id)
        if ext.domain and ext.suffix:
            norm_id = f"{ext.domain}.{ext.suffix}".lower()
    elif payload.identifier_type == "upi":
        norm_id = norm_id.lower()

    # Determine reporter identifier (client IP or forwarded IP)
    forwarded = request.headers.get("X-Forwarded-For")
    reporter_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "127.0.0.1")
    )

    record_report(
        session=db,
        identifier=norm_id,
        identifier_type=payload.identifier_type,
        reporter_id=reporter_ip,
        category=payload.category,
        notes=payload.notes,
    )

    stats = get_report_stats(db, norm_id)
    return ReportResponse(
        status="received",
        identifier_type=payload.identifier_type,
        distinct_reporters=stats["distinct_reporters"],
        total_reports=stats["total_reports"],
        message=f"Report registered. This identifier has now been reported by {stats['distinct_reporters']} independent user(s).",
    )


# Mount frontend static files if directory exists
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

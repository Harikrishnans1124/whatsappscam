"""Brand Registry storage, models, and operations using SQLite + SQLAlchemy."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.config import settings


class Base(DeclarativeBase):
    pass


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_policy: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )

    aliases: Mapped[list[BrandAlias]] = relationship(
        "BrandAlias", back_populates="brand", cascade="all, delete-orphan", lazy="joined"
    )
    legal_names: Mapped[list[BrandLegalName]] = relationship(
        "BrandLegalName", back_populates="brand", cascade="all, delete-orphan", lazy="joined"
    )
    domains: Mapped[list[BrandDomain]] = relationship(
        "BrandDomain", back_populates="brand", cascade="all, delete-orphan", lazy="joined"
    )
    phones: Mapped[list[BrandPhone]] = relationship(
        "BrandPhone", back_populates="brand", cascade="all, delete-orphan", lazy="joined"
    )
    sources: Mapped[list[BrandSource]] = relationship(
        "BrandSource", back_populates="brand", cascade="all, delete-orphan", lazy="joined"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "aliases": [a.alias for a in self.aliases],
            "legal_names": [ln.legal_name for ln in self.legal_names],
            "official_domains": [d.domain for d in self.domains],
            "official_phones": [p.phone_e164 for p in self.phones],
            "payment_policy": self.payment_policy,
            "sources": [{"url": s.url, "verified_on": s.verified_on} for s in self.sources],
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BrandAlias(Base):
    __tablename__ = "brand_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), index=True, nullable=False)

    brand: Mapped[Brand] = relationship("Brand", back_populates="aliases")


class BrandLegalName(Base):
    __tablename__ = "brand_legal_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(300), nullable=False)

    brand: Mapped[Brand] = relationship("Brand", back_populates="legal_names")


class BrandDomain(Base):
    __tablename__ = "brand_domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(200), index=True, nullable=False)

    brand: Mapped[Brand] = relationship("Brand", back_populates="domains")


class BrandPhone(Base):
    __tablename__ = "brand_phones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    brand: Mapped[Brand] = relationship("Brand", back_populates="phones")


class BrandSource(Base):
    __tablename__ = "brand_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    verified_on: Mapped[str] = mapped_column(String(20), nullable=False)  # ISO Date YYYY-MM-DD

    brand: Mapped[Brand] = relationship("Brand", back_populates="sources")


def get_engine(db_url: str | None = None):
    url = db_url or settings.get("database_url", "sqlite:///data/trustshop.db")
    if url.startswith("sqlite:///"):
        db_path = Path(url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, echo=False)


def get_session_factory(engine=None):
    eng = engine or get_engine()
    return sessionmaker(bind=eng, autoflush=False, autocommit=False)


def init_db(engine=None):
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)


def validate_brand_data(data: dict[str, Any]) -> list[str]:
    """Validate a brand dictionary. Returns a list of validation error messages (empty if valid).
    Strictly enforces source URL and verified_on date rules.
    """
    errors: list[str] = []
    slug = data.get("slug")
    if not slug or not isinstance(slug, str) or not slug.strip():
        errors.append("Brand slug is missing or empty")

    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        errors.append(f"Brand '{slug or 'unknown'}': name is missing or empty")

    domains = data.get("official_domains")
    if domains is None or not isinstance(domains, list) or len(domains) == 0:
        errors.append(f"Brand '{slug or 'unknown'}': official_domains must be a non-empty list")

    sources = data.get("sources")
    if not sources or not isinstance(sources, list) or len(sources) == 0:
        errors.append(f"Brand '{slug or 'unknown'}': must have at least one verified source")
    else:
        for idx, src in enumerate(sources):
            if not isinstance(src, dict):
                errors.append(f"Brand '{slug}': source #{idx+1} is not a valid dictionary")
                continue
            url = src.get("url")
            verified_on = src.get("verified_on")
            if not url or not isinstance(url, str) or not url.strip():
                errors.append(f"Brand '{slug}': source #{idx+1} is missing a valid URL")
            if not verified_on or not isinstance(verified_on, str) or not verified_on.strip():
                errors.append(f"Brand '{slug}': source #{idx+1} is missing verified_on date")
            else:
                try:
                    dt.date.fromisoformat(verified_on.strip())
                except ValueError:
                    errors.append(f"Brand '{slug}': verified_on '{verified_on}' is not a valid ISO date (YYYY-MM-DD)")

    return errors


def upsert_brand(session: Session, data: dict[str, Any]) -> Brand:
    """Validate and insert/update a brand in the database."""
    errors = validate_brand_data(data)
    if errors:
        raise ValueError("; ".join(errors))

    slug = data["slug"].strip().lower()
    existing = session.execute(select(Brand).where(Brand.slug == slug)).unique().scalar_one_or_none()

    if existing:
        brand = existing
        brand.name = data["name"].strip()
        brand.payment_policy = data.get("payment_policy", "").strip()
        brand.aliases.clear()
        brand.legal_names.clear()
        brand.domains.clear()
        brand.phones.clear()
        brand.sources.clear()
    else:
        brand = Brand(
            slug=slug,
            name=data["name"].strip(),
            payment_policy=data.get("payment_policy", "").strip(),
        )
        session.add(brand)

    # Aliases
    for alias in data.get("aliases", []):
        if alias and str(alias).strip():
            brand.aliases.append(BrandAlias(alias=str(alias).strip()))

    # Legal names
    for ln in data.get("legal_names", []):
        if ln and str(ln).strip():
            brand.legal_names.append(BrandLegalName(legal_name=str(ln).strip()))

    # Official domains (normalize to lowercase)
    for dom in data.get("official_domains", []):
        if dom and str(dom).strip():
            brand.domains.append(BrandDomain(domain=str(dom).strip().lower()))

    # Official phones
    for ph in data.get("official_phones", []):
        if ph and str(ph).strip():
            brand.phones.append(BrandPhone(phone_e164=str(ph).strip()))

    # Sources
    for src in data.get("sources", []):
        brand.sources.append(
            BrandSource(
                url=src["url"].strip(),
                verified_on=str(src["verified_on"]).strip(),
            )
        )

    session.commit()
    session.refresh(brand)
    return brand


def get_brand_by_slug(session: Session, slug: str) -> Brand | None:
    """Retrieve brand by slug (case-insensitive)."""
    return session.execute(
        select(Brand).where(Brand.slug == slug.strip().lower())
    ).unique().scalar_one_or_none()


def find_brand_by_alias_or_name(session: Session, query: str) -> Brand | None:
    """Look up brand matching name, slug, or any alias."""
    q_norm = query.strip().lower()
    # 1. Exact match on slug
    brand = get_brand_by_slug(session, q_norm)
    if brand:
        return brand

    # 2. Match on brand name
    brand = session.execute(
        select(Brand).where(Brand.name.ilike(q_norm))
    ).unique().scalar_one_or_none()
    if brand:
        return brand

    # 3. Match on alias
    alias_match = session.execute(
        select(BrandAlias).where(BrandAlias.alias.ilike(q_norm))
    ).scalars().first()
    if alias_match:
        return alias_match.brand

    return None


def get_all_brands(session: Session) -> list[Brand]:
    """Fetch all registered brands."""
    return list(session.execute(select(Brand)).unique().scalars().all())


def is_brand_stale(brand: Brand, max_age_days: int = 90, ref_date: dt.date | None = None) -> bool:
    """Check if the brand entry's most recent source verification is older than max_age_days."""
    if not brand.sources:
        return True
    
    reference = ref_date or dt.datetime.now(dt.timezone.utc).date()
    latest_date: dt.date | None = None
    for src in brand.sources:
        try:
            d = dt.date.fromisoformat(src.verified_on)
            if latest_date is None or d > latest_date:
                latest_date = d
        except ValueError:
            continue

    if latest_date is None:
        return True

    age_days = (reference - latest_date).days
    return age_days > max_age_days

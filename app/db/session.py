from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if they don't exist yet. Safe to call on every startup."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()

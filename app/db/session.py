from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

# Columns added to Job after the table already existed in people's real
# databases. create_all() only creates *missing tables* - it silently does
# nothing for a table that exists but is missing a column, so anyone
# with an existing job_hunter.db needs these added by hand. This is a
# lightweight stand-in for Alembic (not used in this project) - a plain
# list of (column, DDL type) pairs, applied idempotently on every startup.
_COLUMN_MIGRATIONS: list[tuple[str, str]] = [
    ("rationale", "TEXT"),
    ("user_id", "INTEGER"),
]


def _migrate_missing_columns() -> None:
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return  # table doesn't exist yet - create_all() will make it fresh, migration not needed
    existing_columns = {col["name"] for col in inspector.get_columns("jobs")}
    with engine.begin() as conn:
        for column_name, ddl_type in _COLUMN_MIGRATIONS:
            if column_name not in existing_columns:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {column_name} {ddl_type}"))


def _backfill_owner_on_jobs() -> None:
    """Jobs created before the user_id column existed have user_id=NULL.
    Attribute all of them to the owner account (see app/auth.py) rather
    than leaving them ownerless and invisible to everyone, including you."""
    from app.auth import get_or_create_owner  # local import: app.auth needs
    # nothing from this module, so this just avoids an unnecessary
    # module-load-time dependency in the common case (a fresh DB with no
    # legacy rows to backfill) rather than a real circular import.

    session = SessionLocal()
    try:
        owner = get_or_create_owner(session)
        session.execute(
            text("UPDATE jobs SET user_id = :owner_id WHERE user_id IS NULL"),
            {"owner_id": owner.id},
        )
        session.commit()
    finally:
        session.close()


def init_db() -> None:
    """Create tables if they don't exist yet, patch missing columns onto
    tables that do, and make sure every job has an owner. Safe to call on
    every startup."""
    Base.metadata.create_all(engine)
    _migrate_missing_columns()
    _backfill_owner_on_jobs()


def get_session() -> Session:
    return SessionLocal()

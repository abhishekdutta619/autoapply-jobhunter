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


def init_db() -> None:
    """Create tables if they don't exist yet, and patch missing columns
    onto tables that do. Safe to call on every startup."""
    Base.metadata.create_all(engine)
    _migrate_missing_columns()


def get_session() -> Session:
    return SessionLocal()

from __future__ import annotations

import importlib
import os
import tempfile

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.fixture()
def old_schema_db_path():
    """A SQLite file with the jobs table as it looked *before* the
    rationale column existed - simulates a real user's pre-existing
    job_hunter.db with ~1,556 already-scraped rows."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                source VARCHAR(32),
                external_id VARCHAR(128),
                title VARCHAR(512),
                company VARCHAR(256),
                location VARCHAR(256),
                description_html TEXT,
                apply_url VARCHAR(1024),
                posted_at DATETIME,
                status VARCHAR(32),
                match_score INTEGER,
                scraped_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            INSERT INTO jobs (source, external_id, title, company, apply_url, status)
            VALUES ('greenhouse', '1', 'Senior Engineer', 'acme', 'https://example.com', 'PENDING_EVALUATION')
        """))
    engine.dispose()
    yield path
    os.unlink(path)


def test_migration_adds_rationale_column_without_losing_data(old_schema_db_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{old_schema_db_path}")
    # init_db() also runs the owner-backfill step now (see app/auth.py),
    # which requires OWNER_EMAIL - unrelated to what this test actually
    # checks (the rationale/user_id column migration), but init_db() does
    # both in one call, so this needs to be set for it to complete.
    monkeypatch.setenv("OWNER_EMAIL", "test-owner@example.com")

    # config.settings and db.session both read DATABASE_URL at import time,
    # so both need a fresh import under the patched env var. app.auth
    # also needs reloading here: it does `from app.config import settings`
    # at module level, binding that specific object - if app.auth was
    # already imported by an earlier test in this process, that binding
    # is stale and won't see OWNER_EMAIL above no matter how many times
    # app.config itself gets reloaded.
    import app.config as config_module
    importlib.reload(config_module)
    import app.auth as auth_module
    importlib.reload(auth_module)
    import app.db.session as session_module
    importlib.reload(session_module)

    session_module.init_db()

    inspector = inspect(session_module.engine)
    columns = {col["name"] for col in inspector.get_columns("jobs")}
    assert "rationale" in columns

    # The pre-existing row must survive the migration untouched.
    with session_module.engine.begin() as conn:
        row = conn.execute(text("SELECT title, status, rationale FROM jobs WHERE id = 1")).fetchone()
    assert row.title == "Senior Engineer"
    assert row.status == "PENDING_EVALUATION"
    assert row.rationale is None  # column added, but no data backfilled - correct, nothing to backfill from

    # Windows holds an OS-level lock on the SQLite file until every
    # connection in the pool is closed - dispose() before the
    # old_schema_db_path fixture's os.unlink() teardown runs, or Windows
    # raises PermissionError [WinError 32]. POSIX allows deleting an
    # open file without complaint, so this was invisible until tested
    # on Windows.
    session_module.engine.dispose()


def test_migration_is_idempotent_on_already_migrated_db(old_schema_db_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{old_schema_db_path}")
    monkeypatch.setenv("OWNER_EMAIL", "test-owner@example.com")

    import app.config as config_module
    importlib.reload(config_module)
    import app.auth as auth_module
    importlib.reload(auth_module)
    import app.db.session as session_module
    importlib.reload(session_module)

    session_module.init_db()
    session_module.init_db()  # running it twice must not raise "duplicate column"

    session_module.engine.dispose()  # see comment in the test above
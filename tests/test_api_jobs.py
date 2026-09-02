from __future__ import annotations

import importlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    """Fresh temp SQLite DB per test, with config/session/api modules
    reloaded against it so nothing leaks between tests or touches a
    real job_hunter.db.

    /api/jobs now requires an authenticated user (see app/api/deps.py's
    get_current_user) and scopes every query to that user's own jobs -
    this fixture overrides that dependency to a fixed test user instead
    of driving a real OAuth flow, which is what FastAPI's own testing
    docs recommend dependency overrides for. _insert_job's default
    user_id matches this fixture's user.id so inserted jobs are actually
    visible to it."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

    import app.config as config_module
    importlib.reload(config_module)
    import app.db.session as session_module
    importlib.reload(session_module)
    import app.api.deps as deps_module
    importlib.reload(deps_module)
    import app.api.routes.jobs as jobs_routes
    importlib.reload(jobs_routes)
    import app.api.main as main_module
    importlib.reload(main_module)

    from app.db.models import Base, User

    # Base.metadata.create_all(), not session_module.init_db() - init_db()
    # also runs the owner-bootstrap/backfill step, which requires
    # OWNER_EMAIL to be set (see app/auth.py's get_or_create_owner) and
    # isn't needed here; these tests manage their own fixed test user.
    Base.metadata.create_all(session_module.engine)

    session = session_module.get_session()
    test_user = User(id=1, email="test@example.com", name="Test User", is_owner=True)
    session.add(test_user)
    session.commit()
    session.close()

    main_module.app.dependency_overrides[deps_module.get_current_user] = lambda: test_user

    with TestClient(main_module.app) as test_client:
        yield test_client, session_module

    main_module.app.dependency_overrides.clear()
    # See test_db_migration.py for why this matters on Windows: an
    # undisposed SQLAlchemy engine holds the SQLite file open, and
    # os.unlink() below raises PermissionError [WinError 32] until
    # every pooled connection is released.
    session_module.engine.dispose()
    os.unlink(path)


def _insert_job(session_module, **overrides):
    from app.db.models import Job, JobStatus

    defaults = dict(
        source="greenhouse",
        external_id="ext-1",
        title="Senior Frontend Engineer",
        company="Doordash",
        apply_url="https://example.com/apply",
        status=JobStatus.PENDING_EVALUATION.value,
        user_id=1,  # matches the client fixture's overridden test user
    )
    defaults.update(overrides)
    session = session_module.get_session()
    job = Job(**defaults)
    session.add(job)
    session.commit()
    session.refresh(job)
    session.close()
    return job.id


def test_health_check(client):
    test_client, _ = client
    resp = test_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_jobs_returns_camelcase_fields(client):
    test_client, session_module = client
    _insert_job(session_module, match_score=78, rationale="Strong overlap")

    resp = test_client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    job = body[0]
    # These are the exact field names core/models/job.model.ts expects.
    assert job["externalId"] == "ext-1"
    assert job["applyUrl"] == "https://example.com/apply"
    assert job["matchScore"] == 78
    assert job["rationale"] == "Strong overlap"
    assert job["scrapedAt"] is not None


def test_list_jobs_filters_by_status(client):
    test_client, session_module = client
    _insert_job(session_module, external_id="a", status="PENDING_EVALUATION")
    _insert_job(session_module, external_id="b", status="APPROVED_FOR_APPLY")

    resp = test_client.get("/api/jobs", params={"status": "APPROVED_FOR_APPLY"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["externalId"] == "b"


def test_get_single_job(client):
    test_client, session_module = client
    job_id = _insert_job(session_module)

    resp = test_client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


def test_get_missing_job_returns_404(client):
    test_client, _ = client
    resp = test_client.get("/api/jobs/999")
    assert resp.status_code == 404


def test_patch_status_approve(client):
    """Exactly what JobReviewCardComponent's Approve button triggers via
    PipelineStore.approve() -> JobApiService.approve()."""
    test_client, session_module = client
    job_id = _insert_job(session_module, status="PENDING_EVALUATION")

    resp = test_client.patch(f"/api/jobs/{job_id}/status", json={"status": "APPROVED_FOR_APPLY"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED_FOR_APPLY"

    # Confirm it actually persisted, not just echoed back.
    resp2 = test_client.get(f"/api/jobs/{job_id}")
    assert resp2.json()["status"] == "APPROVED_FOR_APPLY"


def test_patch_status_reject(client):
    test_client, session_module = client
    job_id = _insert_job(session_module, status="PENDING_EVALUATION")

    resp = test_client.patch(f"/api/jobs/{job_id}/status", json={"status": "TRASHED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "TRASHED"


def test_patch_status_on_missing_job_returns_404(client):
    test_client, _ = client
    resp = test_client.patch("/api/jobs/999/status", json={"status": "TRASHED"})
    assert resp.status_code == 404


def test_patch_status_rejects_invalid_status_value(client):
    test_client, session_module = client
    job_id = _insert_job(session_module)

    resp = test_client.patch(f"/api/jobs/{job_id}/status", json={"status": "NOT_A_REAL_STATUS"})
    assert resp.status_code == 422


def test_websocket_connects_and_accepts_kill_switch_message(client):
    """Matches JobSocketService.connect() + killSwitch() in the Angular
    client: connect to /ws/executor/{id}, then send {action: 'kill', jobId}."""
    test_client, _ = client
    import app.api.ws.manager as manager_module

    with test_client.websocket_connect("/ws/executor/42") as ws:
        assert not manager_module.manager.is_kill_requested(42)
        ws.send_json({"action": "kill", "jobId": 42})
        import time
        time.sleep(0.05)
        # Assert while still connected - disconnect (below, on context exit)
        # clears the flag by design, see test_websocket_disconnect_clears_kill_flag.
        assert manager_module.manager.is_kill_requested(42)


def test_websocket_disconnect_clears_kill_flag(client):
    test_client, _ = client
    import app.api.ws.manager as manager_module

    with test_client.websocket_connect("/ws/executor/7") as ws:
        ws.send_json({"action": "kill", "jobId": 7})
        import time
        time.sleep(0.05)

    # disconnect() clears the flag for that job_id - a fresh connection
    # for the same job later shouldn't inherit a stale kill request.
    assert not manager_module.manager.is_kill_requested(7)
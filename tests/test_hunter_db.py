from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Job, JobStatus
from app.hunter import upsert_job
from app.sources.base import RawJob


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    yield s
    s.close()


def _raw(**overrides):
    base = dict(
        source="greenhouse",
        external_id="123",
        title="Software Engineer",
        company="acme",
        location="Remote",
        description_html="<p>desc</p>",
        apply_url="https://example.com/apply",
        posted_at=None,
    )
    base.update(overrides)
    return RawJob(**base)


def test_new_job_is_inserted_as_pending(session):
    was_new = upsert_job(session, _raw(), owner_id=1)
    session.commit()

    assert was_new is True
    job = session.scalar(select(Job))
    assert job.status == JobStatus.PENDING_EVALUATION.value
    assert job.title == "Software Engineer"


def test_same_source_and_external_id_is_not_duplicated(session):
    upsert_job(session, _raw(), owner_id=1)
    session.commit()
    upsert_job(session, _raw(), owner_id=1)
    session.commit()

    count = session.scalar(select(Job)).id
    all_jobs = session.scalars(select(Job)).all()
    assert len(all_jobs) == 1


def test_re_seen_job_updates_fields_without_resetting_status(session):
    upsert_job(session, _raw(title="Old Title"), owner_id=1)
    session.commit()

    job = session.scalar(select(Job))
    job.status = JobStatus.APPROVED_FOR_APPLY.value
    session.commit()

    was_new = upsert_job(session, _raw(title="New Title"), owner_id=1)
    session.commit()

    assert was_new is False
    refreshed = session.scalar(select(Job))
    assert refreshed.title == "New Title"
    # Status is owned by the Evaluator/Executor phases, not the Hunter.
    assert refreshed.status == JobStatus.APPROVED_FOR_APPLY.value


def test_same_external_id_different_source_is_distinct(session):
    upsert_job(session, _raw(source="greenhouse", external_id="123"), owner_id=1)
    upsert_job(session, _raw(source="lever", external_id="123"), owner_id=1)
    session.commit()

    all_jobs = session.scalars(select(Job)).all()
    assert len(all_jobs) == 2

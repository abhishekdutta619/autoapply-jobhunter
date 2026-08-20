from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Job, JobStatus
from app.inspect_jobs import recent_jobs, status_counts


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    yield s
    s.close()


def _job(i: int, status: str) -> Job:
    return Job(
        source="greenhouse",
        external_id=str(i),
        title=f"Job {i}",
        company="acme",
        apply_url="https://example.com",
        status=status,
    )


def test_status_counts_groups_correctly(session):
    session.add_all(
        [
            _job(1, JobStatus.PENDING_EVALUATION.value),
            _job(2, JobStatus.PENDING_EVALUATION.value),
            _job(3, JobStatus.APPROVED_FOR_APPLY.value),
        ]
    )
    session.commit()

    counts = status_counts(session)
    assert counts[JobStatus.PENDING_EVALUATION.value] == 2
    assert counts[JobStatus.APPROVED_FOR_APPLY.value] == 1


def test_recent_jobs_filters_by_status(session):
    session.add_all(
        [
            _job(1, JobStatus.APPROVED_FOR_APPLY.value),
            _job(2, JobStatus.TRASHED.value),
        ]
    )
    session.commit()

    approved = recent_jobs(session, status=JobStatus.APPROVED_FOR_APPLY.value)
    assert len(approved) == 1
    assert approved[0].external_id == "1"


def test_recent_jobs_respects_limit(session):
    session.add_all([_job(i, JobStatus.PENDING_EVALUATION.value) for i in range(5)])
    session.commit()

    jobs = recent_jobs(session, limit=2)
    assert len(jobs) == 2

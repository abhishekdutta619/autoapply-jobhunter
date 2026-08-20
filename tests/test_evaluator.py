from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Job, JobStatus
from app.evaluator import evaluate_job
from app.llm.base import EvaluationResult


class StubLLMClient:
    """Returns a fixed score every time - no network, fully deterministic."""

    def __init__(self, score: int, reasoning: str = "stub reasoning"):
        self.score = score
        self.reasoning = reasoning
        self.calls = []

    def evaluate_match(self, resume, job_title, job_description):
        self.calls.append((resume, job_title, job_description))
        return EvaluationResult(score=self.score, reasoning=self.reasoning)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    yield s
    s.close()


def _pending_job(**overrides) -> Job:
    defaults = dict(
        source="greenhouse",
        external_id="1",
        title="Senior Backend Engineer",
        company="acme",
        apply_url="https://example.com",
        status=JobStatus.PENDING_EVALUATION.value,
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_high_score_is_approved(session):
    job = _pending_job()
    session.add(job)
    session.commit()

    evaluate_job(job, StubLLMClient(score=90), "resume text", threshold=85)

    assert job.status == JobStatus.APPROVED_FOR_APPLY.value
    assert job.match_score == 90


def test_low_score_is_trashed(session):
    job = _pending_job()
    session.add(job)
    session.commit()

    evaluate_job(job, StubLLMClient(score=40), "resume text", threshold=85)

    assert job.status == JobStatus.TRASHED.value
    assert job.match_score == 40


def test_score_exactly_at_threshold_is_trashed(session):
    # Original spec: approve only jobs scoring *above* the threshold.
    job = _pending_job()
    session.add(job)
    session.commit()

    evaluate_job(job, StubLLMClient(score=85), "resume text", threshold=85)

    assert job.status == JobStatus.TRASHED.value


def test_resume_and_job_content_are_passed_to_llm(session):
    job = _pending_job(title="Data Engineer", description_html="<p>Airflow, dbt</p>")
    session.add(job)
    session.commit()

    stub = StubLLMClient(score=99)
    evaluate_job(job, stub, "my resume", threshold=85)

    resume_arg, title_arg, description_arg = stub.calls[0]
    assert resume_arg == "my resume"
    assert title_arg == "Data Engineer"
    assert description_arg == "<p>Airflow, dbt</p>"

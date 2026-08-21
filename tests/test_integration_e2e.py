from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Job, JobStatus
from app.evaluator import evaluate_job
from app.executor.candidate import CandidateProfile
from app.hunter import upsert_job
from app.llm.base import DropdownSelection, EvaluationResult
from app.sources.base import RawJob

playwright_sync = pytest.importorskip("playwright.sync_api")

from app.executor.runner import fill_application  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FORM_PATH = FIXTURES_DIR / "sample_application_form.html"
DUMMY_RESUME_PATH = FIXTURES_DIR / "dummy_resume.pdf"


class StubLLMClient:
    """One stub standing in for a real provider across all three of its
    uses (scoring, answer drafting, dropdown mapping) - this test is about
    proving the phases hand off to each other correctly, not re-testing
    LLM parsing, which is already covered in test_llm_clients.py.
    """

    def __init__(self, score: int):
        self.score = score

    def evaluate_match(self, resume, job_title, job_description):
        return EvaluationResult(score=self.score, reasoning="stub reasoning")

    def draft_answer(self, question, story_title, story_text, job_title, job_description):
        return f"Stub answer for: {question}"

    def select_dropdown_option(self, question, options, candidate_context):
        return DropdownSelection(selected_option="NONE", confidence="low")


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def candidate() -> CandidateProfile:
    return CandidateProfile(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="555-123-4567",
        linkedin_url="https://linkedin.com/in/janedoe",
        resume_file_path=str(DUMMY_RESUME_PATH),
    )


def test_job_flows_correctly_from_hunter_through_evaluator_to_executor(session, candidate):
    """Simulates one job's full lifecycle using the real functions each
    phase's CLI actually calls - upsert_job(), evaluate_job(),
    fill_application() - just without their I/O wrappers (no real HTTP,
    no real LLM API, no real DB file, no live site). This is the one
    thing the per-phase test files don't prove: that Phase 2 can actually
    consume what Phase 1 produced, and Phase 3 can actually consume what
    Phase 2 approved.
    """
    # --- Phase 1: Hunter scrapes a posting and inserts it ---
    raw_job = RawJob(
        source="greenhouse",
        external_id="e2e-999",
        title="Senior Backend Engineer",
        company="acme",
        location="Remote - US",
        description_html="5+ years Python, distributed systems experience required.",
        apply_url=f"file://{FORM_PATH}",
    )
    was_new = upsert_job(session, raw_job)
    session.commit()
    assert was_new is True

    job = session.scalar(select(Job).where(Job.external_id == "e2e-999"))
    assert job is not None
    assert job.status == JobStatus.PENDING_EVALUATION.value
    assert job.match_score is None

    # --- Phase 2: Evaluator scores it against a resume and approves it ---
    evaluate_job(
        job,
        StubLLMClient(score=95),
        resume_text="5 years of Python backend experience.",
        threshold=85,
    )
    session.commit()

    assert job.status == JobStatus.APPROVED_FOR_APPLY.value
    assert job.match_score == 95

    # --- Phase 3: Executor opens the job's own apply_url and fills it ---
    # Using the job's real apply_url (not a hardcoded test URL) is the
    # point - it proves Phase 3 correctly consumes what Phase 1 stored.
    with playwright_sync.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(job.apply_url)

        filled, skipped = fill_application(
            page,
            candidate,
            dry_run=False,
            job_title=job.title,
            job_description=job.description_html,
        )

        assert page.input_value("#first_name") == "Jane"
        assert page.input_value("#last_name") == "Doe"
        assert page.input_value("#email") == "jane.doe@example.com"
        assert page.input_value("#linkedin") == "https://linkedin.com/in/janedoe"
        assert len(filled) >= 4

        browser.close()

    # The real runner.py sets APPLYING, then asks the human whether they
    # actually submitted before setting APPLIED/reverting - that step is
    # deliberately interactive (input()) and correctly out of scope for
    # an automated test. Everything up to "browser open for human review"
    # is what this test verifies.


def test_low_score_job_never_reaches_the_executor_stage(session):
    """The inverse path: a job that fails Phase 2 should never end up in
    a state Phase 3 would act on.
    """
    raw_job = RawJob(
        source="lever",
        external_id="e2e-low-score",
        title="Marketing Intern",
        company="acme",
        apply_url="https://example.com/apply",
    )
    upsert_job(session, raw_job)
    session.commit()
    job = session.scalar(select(Job).where(Job.external_id == "e2e-low-score"))

    evaluate_job(
        job, StubLLMClient(score=20), resume_text="5 years of Python experience.", threshold=85
    )
    session.commit()

    assert job.status == JobStatus.TRASHED.value
    # Phase 3's Hunter query (`WHERE status = APPROVED_FOR_APPLY`) would
    # never select this job - proven directly, not just implied.
    from app.executor.runner import pick_job

    assert pick_job(session, job_id=None) is None

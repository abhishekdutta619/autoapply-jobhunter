from __future__ import annotations

from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

from app.executor.candidate import CandidateProfile  # noqa: E402
from app.executor.runner import fill_application  # noqa: E402
from app.rag.story_bank import Story  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FORM_PATH = FIXTURES_DIR / "sample_application_form.html"
DUMMY_RESUME_PATH = FIXTURES_DIR / "dummy_resume.pdf"


@pytest.fixture()
def candidate() -> CandidateProfile:
    return CandidateProfile(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="555-123-4567",
        linkedin_url="https://linkedin.com/in/janedoe",
        github_url="https://github.com/janedoe",
        portfolio_url="https://janedoe.dev",
        resume_file_path=str(DUMMY_RESUME_PATH),
    )


@pytest.fixture()
def page():
    """Provides a Playwright page loaded with the local fixture form.

    Skips (not fails) if no Chromium binary is installed - this test needs
    `playwright install chromium` run once, which this sandbox's network
    restrictions don't allow. Run it locally to actually verify DOM
    interaction; `test_field_classifier.py` covers the decision logic
    itself and runs everywhere.
    """
    try:
        with playwright_sync.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            pg = browser.new_page()
            pg.goto(f"file://{FORM_PATH}")
            yield pg
            browser.close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Chromium not available in this environment: {exc}")


def test_known_fields_are_filled_correctly(page, candidate):
    filled, skipped = fill_application(page, candidate, dry_run=False)

    assert page.input_value("#first_name") == "Jane"
    assert page.input_value("#last_name") == "Doe"
    assert page.input_value("#email") == "jane.doe@example.com"
    assert page.input_value("#phone") == "555-123-4567"
    assert page.input_value("#linkedin") == "https://linkedin.com/in/janedoe"
    assert page.input_value("#github") == "https://github.com/janedoe"
    assert page.input_value("#portfolio") == "https://janedoe.dev"

    uploaded_filename = page.eval_on_selector(
        "#resume_upload", "el => el.files.length ? el.files[0].name : ''"
    )
    assert uploaded_filename == "dummy_resume.pdf"


def test_decoy_company_name_field_is_left_blank(page, candidate):
    fill_application(page, candidate, dry_run=False)
    # This is the critical negative case: a field containing "name" that is
    # NOT the candidate's own name must never get auto-filled.
    assert page.input_value("#company_name") == ""


def test_unmappable_dropdown_is_skipped_and_reported(page, candidate):
    filled, skipped = fill_application(page, candidate, dry_run=False)
    assert any("hear about us" in label.lower() for label in skipped)


def test_cover_letter_and_open_question_are_left_for_human_without_answer_service(page, candidate):
    # Default behavior (answer_service=None): nothing gets fabricated.
    filled, skipped = fill_application(page, candidate, dry_run=False)
    assert page.input_value("#cover_letter_text") == ""
    assert page.input_value("#why_role") == ""
    assert any("cover letter" in label.lower() for label in skipped)
    assert any("why do you want" in label.lower() for label in skipped)


class _StubAnswerService:
    """Fixed response, no LLM/retrieval call - isolates the DOM-fill wiring
    from RAG's own logic, which is tested separately in test_answer_service.py.
    """

    def draft_answer(self, question, job_title, job_description):
        return "Drafted answer text.", Story(title="Stub Story", text="stub")


def test_cover_letter_is_drafted_via_rag_when_answer_service_provided(page, candidate):
    filled, skipped = fill_application(
        page, candidate, dry_run=False,
        answer_service=_StubAnswerService(),
        job_title="Backend Engineer", job_description="Build things",
    )

    assert page.input_value("#cover_letter_text") == "Drafted answer text."
    assert page.input_value("#why_role") == "Drafted answer text."
    assert any("REVIEW BEFORE SUBMITTING" in line for line in filled)


def test_dry_run_does_not_call_answer_service_side_effects(page, candidate):
    # Even with an answer_service provided, dry-run must not write anything.
    fill_application(
        page, candidate, dry_run=True,
        answer_service=_StubAnswerService(),
        job_title="Backend Engineer", job_description="Build things",
    )
    assert page.input_value("#cover_letter_text") == ""
    assert page.input_value("#why_role") == ""


class _StubDropdownMapper:
    """Always picks 'LinkedIn' - isolates the DOM-fill wiring from the
    mapper's own confidence/validity logic, which is tested separately in
    test_dropdown_mapper.py. Records every question it was asked, so tests
    can assert the sensitive field was never even sent to it.
    """

    def __init__(self):
        self.questions_asked: list[str] = []

    def map_option(self, question, options):
        self.questions_asked.append(question)
        return "LinkedIn" if "LinkedIn" in options else None


def test_dropdown_is_filled_via_llm_mapper_when_provided(page, candidate):
    mapper = _StubDropdownMapper()
    filled, skipped = fill_application(page, candidate, dry_run=False, dropdown_mapper=mapper)

    selected_text = page.eval_on_selector(
        "#how_heard", "el => el.options[el.selectedIndex].text"
    )
    assert selected_text == "LinkedIn"
    assert any("LLM PICK" in line for line in filled)


def test_sensitive_dropdown_is_never_sent_to_the_mapper(page, candidate):
    mapper = _StubDropdownMapper()
    fill_application(page, candidate, dry_run=False, dropdown_mapper=mapper)

    # The work-authorization field must never even reach the mapper.
    assert not any("authorized to work" in q.lower() for q in mapper.questions_asked)

    # And its selection in the DOM must remain untouched (still the
    # placeholder, not "Yes" or "No").
    selected_text = page.eval_on_selector(
        "#work_auth", "el => el.options[el.selectedIndex].text"
    )
    assert selected_text == "Select..."


def test_dropdown_without_mapper_is_left_for_human(page, candidate):
    filled, skipped = fill_application(page, candidate, dry_run=False)
    selected_text = page.eval_on_selector(
        "#how_heard", "el => el.options[el.selectedIndex].text"
    )
    assert selected_text == "Select..."
    assert any("hear about us" in label.lower() for label in skipped)


def test_dry_run_reports_without_touching_the_page(page, candidate):
    filled, skipped = fill_application(page, candidate, dry_run=True)
    assert len(filled) > 0  # classification still happened
    assert page.input_value("#first_name") == ""  # but nothing was written

from __future__ import annotations

import argparse
import logging

from playwright.sync_api import Page, sync_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Job, JobStatus
from app.db.session import get_session, init_db
from app.evaluator import load_resume
from app.executor.candidate import CandidateProfile, load_candidate_profile
from app.executor.dropdown_mapper import DropdownMapper
from app.executor.field_classifier import (
    FieldInfo,
    FieldRole,
    classify_field,
    is_sensitive_dropdown,
    resolve_value,
)
from app.llm.factory import get_llm_client
from app.rag.answer_service import AnswerService
from app.rag.retriever import StoryRetriever
from app.rag.story_bank import load_stories

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("executor")

# Runs once per page: tags every input/textarea/select with a stable index
# so Python can re-select the exact same element after inspecting it, and
# extracts the metadata classify_field() needs to make a decision.
EXTRACT_FIELDS_JS = """
() => {
  const fields = Array.from(document.querySelectorAll('input, textarea, select'));
  return fields.map((el, i) => {
    el.setAttribute('data-hunter-idx', String(i));
    let labelText = '';
    if (el.labels && el.labels.length) {
      labelText = Array.from(el.labels).map(l => l.innerText).join(' ');
    }
    let options = [];
    if (el.tagName.toLowerCase() === 'select') {
      // Skip placeholder options (empty value, e.g. <option value="">Select...</option>)
      options = Array.from(el.options)
        .filter(o => o.value && o.value.trim().length > 0)
        .map(o => o.text.trim());
    }
    return {
      idx: i,
      tag: el.tagName.toLowerCase(),
      input_type: (el.getAttribute('type') || '').toLowerCase(),
      name: el.getAttribute('name') || '',
      field_id: el.getAttribute('id') || '',
      placeholder: el.getAttribute('placeholder') || '',
      aria_label: el.getAttribute('aria-label') || '',
      label_text: labelText.trim(),
      options: options,
    };
  });
}
"""


def pick_job(session: Session, job_id: int | None) -> Job | None:
    if job_id is not None:
        return session.get(Job, job_id)
    return session.scalars(
        select(Job)
        .where(Job.status == JobStatus.APPROVED_FOR_APPLY.value)
        .order_by(Job.scraped_at.asc())
        .limit(1)
    ).first()


def fill_application(
    page: Page,
    candidate: CandidateProfile,
    dry_run: bool,
    answer_service: AnswerService | None = None,
    dropdown_mapper: DropdownMapper | None = None,
    job_title: str = "",
    job_description: str = "",
) -> tuple[list[str], list[str]]:
    """Classify and fill every field Playwright can find. Returns
    (filled_descriptions, skipped_labels) for reporting to the human.

    answer_service, if provided, drafts cover-letter / open-question text
    via RAG instead of skipping those fields.

    dropdown_mapper, if provided, asks an LLM to pick a <select> option for
    fields the heuristic classifier couldn't place - except EEO/work-
    authorization questions, which are never sent to the LLM at all,
    regardless of whether a mapper is configured.

    Both are optional and default to None: without them, unmatched fields
    are simply left for the human, same as the original heuristic-only
    behavior.
    """
    raw_fields = page.evaluate(EXTRACT_FIELDS_JS)
    filled: list[str] = []
    skipped: list[str] = []

    for raw in raw_fields:
        info = FieldInfo(**{k: v for k, v in raw.items() if k != "idx"})
        role = classify_field(info)
        label = info.label_text or info.placeholder or info.name or info.field_id or f"field#{raw['idx']}"
        selector = f'[data-hunter-idx="{raw["idx"]}"]'

        if role is None:
            if (
                dropdown_mapper is not None
                and info.tag == "select"
                and info.options
                and not is_sensitive_dropdown(info)
            ):
                selected = dropdown_mapper.map_option(question=label, options=info.options)
                if selected is not None:
                    if not dry_run:
                        page.select_option(selector, label=selected)
                    filled.append(
                        f"{label!r} -> dropdown "
                        f"(LLM PICK: {selected!r} - REVIEW BEFORE SUBMITTING)"
                    )
                    continue
            skipped.append(label)
            continue

        if role == FieldRole.RESUME_UPLOAD:
            value_desc = candidate.resume_file_path
            if not dry_run:
                page.set_input_files(selector, candidate.resume_file_path)
        elif role == FieldRole.COVER_LETTER_UPLOAD:
            if not candidate.cover_letter_file_path:
                skipped.append(label)
                continue
            value_desc = candidate.cover_letter_file_path
            if not dry_run:
                page.set_input_files(selector, candidate.cover_letter_file_path)
        elif role in (FieldRole.COVER_LETTER_TEXT, FieldRole.OPEN_QUESTION_TEXT):
            if answer_service is None:
                # No story bank / LLM configured - leave for the human
                # rather than fabricating an answer with no grounding.
                skipped.append(label)
                continue
            try:
                answer, story = answer_service.draft_answer(
                    question=label, job_title=job_title, job_description=job_description
                )
            except Exception as exc:  # noqa: BLE001
                skipped.append(f"{label} (answer drafting failed: {exc})")
                continue
            value_desc = f"AI DRAFT from story {story.title!r} - REVIEW BEFORE SUBMITTING"
            if not dry_run:
                page.fill(selector, answer)
        else:
            value = resolve_value(role, candidate)
            if not value:
                skipped.append(label)
                continue
            value_desc = value
            if not dry_run:
                page.fill(selector, value)

        filled.append(f"{label!r} -> {role.value} ({value_desc})")

    return filled, skipped


def _print_report(filled: list[str], skipped: list[str]) -> None:
    print("\n=== Filled ===")
    for line in filled:
        print(f"  \u2713 {line}")
    print("\n=== Skipped - needs your review ===")
    for line in skipped:
        print(f"  - {line}")
    print()


def _build_answer_service() -> AnswerService | None:
    try:
        stories = load_stories()
    except FileNotFoundError:
        log.info(
            "No story bank found - cover letter / open-question fields will "
            "be skipped, not drafted. See story_bank.json.example if you "
            "want RAG-drafted answers."
        )
        return None
    retriever = StoryRetriever(stories)
    llm_client = get_llm_client()
    return AnswerService(retriever, llm_client)


def _build_dropdown_mapper() -> DropdownMapper | None:
    try:
        resume_text = load_resume()
    except FileNotFoundError:
        log.info(
            "No resume.md found - dropdown fields the classifier can't "
            "place will be skipped, not LLM-mapped."
        )
        return None
    llm_client = get_llm_client()
    return DropdownMapper(llm_client, resume_text)


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Open an approved job application and pre-fill known fields. "
        "Never submits - you review and click submit yourself."
    )
    parser.add_argument(
        "--job-id", type=int, default=None,
        help="Specific job ID to apply to. Defaults to the oldest APPROVED_FOR_APPLY job.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Classify fields and report what WOULD be filled, without touching the page.",
    )
    args = parser.parse_args()

    init_db()
    candidate = load_candidate_profile()
    answer_service = _build_answer_service()
    dropdown_mapper = _build_dropdown_mapper()
    session = get_session()

    job = pick_job(session, args.job_id)
    if job is None:
        log.info("No matching APPROVED_FOR_APPLY job found. Run the Evaluator first.")
        session.close()
        return

    log.info("Opening application for: %s at %s", job.title, job.company)
    log.info("Apply URL: %s", job.apply_url)

    if not args.dry_run:
        job.status = JobStatus.APPLYING.value
        session.commit()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.executor_headless)
            page = browser.new_page()
            page.goto(job.apply_url, wait_until="domcontentloaded")

            filled, skipped = fill_application(
                page, candidate, args.dry_run,
                answer_service=answer_service,
                dropdown_mapper=dropdown_mapper,
                job_title=job.title,
                job_description=job.description_html or "",
            )
            _print_report(filled, skipped)

            if args.dry_run:
                log.info("Dry run complete - nothing was filled or submitted.")
                browser.close()
                session.close()
                return

            screenshot_path = f"executor_review_job{job.id}.png"
            page.screenshot(path=screenshot_path, full_page=True)
            log.info("Screenshot saved to %s for your records.", screenshot_path)

            input(
                "\nReview the open browser window: check every filled field, "
                "answer anything left blank (dropdowns, EEO/demographic "
                "questions, work authorization, etc.), then submit the "
                "application yourself if it looks right.\n"
                "Press Enter here once you're done (whether you submitted or not)..."
            )
            browser.close()
    except Exception:
        log.exception(
            "Executor run failed - reverting job to APPROVED_FOR_APPLY so it can be retried."
        )
        if not args.dry_run:
            job.status = JobStatus.APPROVED_FOR_APPLY.value
            session.commit()
        session.close()
        raise

    submitted = input("Did you actually submit the application? [y/N] ").strip().lower() == "y"
    job.status = JobStatus.APPLIED.value if submitted else JobStatus.APPROVED_FOR_APPLY.value
    session.commit()
    session.close()
    log.info("Job marked as %s.", job.status)


if __name__ == "__main__":
    run()

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Job, JobStatus
from app.db.session import get_session, init_db
from app.text_utils import strip_html
from app.llm.base import LLMClient
from app.llm.factory import get_llm_client
from app.llm.prompts import build_constraints_section

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("evaluator")


def load_resume(path: str = None) -> str:
    resume_path = Path(path or settings.resume_path)
    if not resume_path.exists():
        raise FileNotFoundError(
            f"No resume found at {resume_path}. Copy resume.md.example to "
            f"{resume_path} and fill in your real resume before running "
            "the Evaluator."
        )
    text = resume_path.read_text().strip()
    if not text:
        raise ValueError(f"{resume_path} is empty.")
    return text


def evaluate_job(
    job: Job,
    llm_client: LLMClient,
    resume_text: str,
    threshold: int,
    review_threshold: int | None = None,
) -> None:
    """Score one job and update its status in place. Caller commits.

    review_threshold=None (the default) reproduces the original hard-cutoff
    behavior exactly: score > threshold approves, everything else trashes.
    Passing a review_threshold below `threshold` introduces a middle band -
    scores in [review_threshold, threshold] stay PENDING_EVALUATION with
    match_score and rationale populated, so a human can decide via the
    dashboard's review queue instead of the job being silently discarded.
    """
    result = llm_client.evaluate_match(
        resume=resume_text,
        job_title=job.title,
        job_description=strip_html(job.description_html),
    )
    job.match_score = result.score
    job.rationale = result.reasoning

    if result.score > threshold:
        job.status = JobStatus.APPROVED_FOR_APPLY.value
    elif review_threshold is not None and result.score >= review_threshold:
        job.status = JobStatus.PENDING_EVALUATION.value
    else:
        job.status = JobStatus.TRASHED.value

    log.info(
        "%-40s score=%3d -> %s",
        job.title[:40], result.score, job.status,
    )


def run(limit: int | None = None) -> None:
    init_db()
    resume_text = load_resume()
    # Folded into the resume text itself (not a new evaluate_match()
    # parameter) so this works identically across all four LLM clients
    # with zero changes to any of them. No-op ("") if nothing is configured.
    resume_text += build_constraints_section(
        settings.prefer_remote,
        settings.target_compensation_indian,
        settings.target_compensation_mnc,
    )
    llm_client = get_llm_client()
    session: Session = get_session()

    evaluated = 0
    approved = 0
    queued_for_review = 0
    failed = 0

    try:
        # match_score.is_(None) matters as of the review-band change: a job
        # can be status=PENDING_EVALUATION *and* already scored (sitting in
        # the review queue for a human). Without this filter, re-running the
        # Evaluator would re-score - and burn API calls on - every job
        # already waiting for manual review.
        query = select(Job).where(
            Job.status == JobStatus.PENDING_EVALUATION.value,
            Job.match_score.is_(None),
        )
        if limit is not None:
            query = query.limit(limit)
        pending = session.scalars(query).all()

        if not pending:
            log.info("No unevaluated jobs pending. Run the Hunter first.")
            return

        if limit is not None:
            total_pending = session.scalar(
                select(func.count(Job.id)).where(
                    Job.status == JobStatus.PENDING_EVALUATION.value,
                    Job.match_score.is_(None),
                )
            )
            log.info(
                "Evaluating %d of %d unevaluated pending jobs (--limit %d set).",
                len(pending), total_pending, limit,
            )

        for job in pending:
            try:
                evaluate_job(
                    job, llm_client, resume_text,
                    settings.approval_threshold, settings.review_threshold,
                )
                session.commit()
                evaluated += 1
                if job.status == JobStatus.APPROVED_FOR_APPLY.value:
                    approved += 1
                elif job.status == JobStatus.PENDING_EVALUATION.value:
                    queued_for_review += 1
            except Exception as exc:  # noqa: BLE001 - one bad job shouldn't kill the run
                session.rollback()
                failed += 1
                log.error("Failed evaluating job id=%s: %s", job.id, exc)
                # Status is left untouched (still PENDING_EVALUATION, still
                # match_score=None) so this job gets retried on the next run.

            time.sleep(settings.eval_request_delay_seconds)
    finally:
        session.close()

    log.info(
        "Done. %d evaluated, %d approved, %d queued for review, %d failed/skipped.",
        evaluated, approved, queued_for_review, failed,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Score PENDING_EVALUATION jobs against your resume via LLM."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only evaluate this many jobs (useful for a first sanity-check "
        "run before committing to the full pending queue's API cost/time).",
    )
    args = parser.parse_args()
    run(limit=args.limit)
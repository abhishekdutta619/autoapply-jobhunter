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
from app.llm.base import LLMClient
from app.llm.factory import get_llm_client

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
    job: Job, llm_client: LLMClient, resume_text: str, threshold: int
) -> None:
    """Score one job and update its status in place. Caller commits."""
    result = llm_client.evaluate_match(
        resume=resume_text,
        job_title=job.title,
        job_description=job.description_html or "",
    )
    job.match_score = result.score
    job.status = (
        JobStatus.APPROVED_FOR_APPLY.value
        if result.score > threshold
        else JobStatus.TRASHED.value
    )
    log.info(
        "%-40s score=%3d -> %s",
        job.title[:40], result.score, job.status,
    )


def run(limit: int | None = None) -> None:
    init_db()
    resume_text = load_resume()
    llm_client = get_llm_client()
    session: Session = get_session()

    evaluated = 0
    approved = 0
    failed = 0

    try:
        query = select(Job).where(Job.status == JobStatus.PENDING_EVALUATION.value)
        if limit is not None:
            query = query.limit(limit)
        pending = session.scalars(query).all()

        if not pending:
            log.info("No jobs pending evaluation. Run the Hunter first.")
            return

        if limit is not None:
            total_pending = session.scalar(
                select(func.count(Job.id)).where(
                    Job.status == JobStatus.PENDING_EVALUATION.value
                )
            )
            log.info(
                "Evaluating %d of %d pending jobs (--limit %d set).",
                len(pending), total_pending, limit,
            )

        for job in pending:
            try:
                evaluate_job(job, llm_client, resume_text, settings.approval_threshold)
                session.commit()
                evaluated += 1
                if job.status == JobStatus.APPROVED_FOR_APPLY.value:
                    approved += 1
            except Exception as exc:  # noqa: BLE001 - one bad job shouldn't kill the run
                session.rollback()
                failed += 1
                log.error("Failed evaluating job id=%s: %s", job.id, exc)
                # Status is left untouched (still PENDING_EVALUATION) so
                # this job gets retried on the next run.

            time.sleep(settings.eval_request_delay_seconds)
    finally:
        session.close()

    log.info(
        "Done. %d evaluated, %d approved, %d failed/skipped.",
        evaluated, approved, failed,
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
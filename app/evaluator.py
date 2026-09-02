from __future__ import annotations

import argparse
import logging
import re
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


# --- Fast pre-filter (runs before any LLM call) ---------------------------
# Deliberately biased toward false positives (letting an ambiguous job
# through to the LLM) over false negatives (silently discarding a good
# match, with no human ever seeing it) - the cost of being wrong the "let
# it through" way is one ~2.5min local-model call; the cost of being wrong
# the "skip it" way is a job that disappears from the pipeline entirely.

# Title-only, deliberately short and conservative - unambiguous
# non-engineering roles only. Checked against title alone, never the
# description, to keep this a narrow, low-risk signal.
EXCLUDE_TITLE_KEYWORDS = [
    "sales", "account executive", "recruiter", "talent acquisition",
    "accountant", "bookkeeper", "human resources", "hr generalist",
    "marketing manager", "executive assistant", "office manager",
    "customer support", "content writer", "paralegal",
]

# Broad on purpose: this is a "does this look like a tech job at all"
# check, not "does this match my exact stack" - that judgment stays with
# the LLM. A job is only skipped by this list if it matches NONE of these
# anywhere in title+description.
SKILL_KEYWORDS = [
    # languages
    "javascript", "typescript", "python", "java", "c++", "c#", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "objective-c",
    "dart", "elixir", "haskell", "clojure", "perl", "bash", "shell",
    "sql", "html", "css", "sass", "less",
    # frontend
    "react", "redux", "angular", "vue", "svelte", "next.js", "nuxt",
    "jquery", "mobx", "tailwind", "bootstrap", "material ui", "ember",
    "backbone", "webcomponents", "web components",
    # backend
    "node.js", "nodejs", "express", "nestjs", "fastapi", "django",
    "flask", "spring", "spring boot", "ruby on rails", "rails",
    "laravel", ".net", "asp.net", "gin framework", "echo framework",
    # mobile
    "ios development", "android development", "react native", "flutter",
    "xamarin", "ionic", "swiftui", "jetpack compose", "mobile app",
    "mobile developer", "mobile engineer",
    # databases
    "mongodb", "postgresql", "postgres", "mysql", "sqlite", "redis",
    "cassandra", "dynamodb", "firebase", "firestore", "graphql",
    "elasticsearch",
    # cloud / devops
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes",
    "terraform", "ci/cd", "jenkins", "github actions", "gitlab ci",
    "microservices", "serverless",
    # tooling
    "git", "webpack", "vite", "babel", "npm", "yarn", "jest", "mocha",
    "cypress", "selenium", "postman", "rest api", "restful",
    # generic role/domain signals
    "software engineer", "software developer", "web developer",
    "application developer", "systems engineer", "devops engineer",
    "site reliability", "platform engineer", "frontend", "front-end",
    "front end", "backend", "back-end", "back end", "full stack",
    "fullstack", "ui developer", "ux developer", "single page application",
    "progressive web app", "api development", "sdk",
]

_WORD_RE_CACHE: dict[str, re.Pattern] = {}


def _keyword_in(keyword: str, haystack: str) -> bool:
    """Plain substring match, except for short single-word tokens (<4
    chars) where `in` would false-positive on almost any text (e.g. a bare
    "go" or "r" matching inside unrelated words) - those get a
    word-boundary regex instead."""
    if len(keyword) < 4 and " " not in keyword:
        pattern = _WORD_RE_CACHE.setdefault(
            keyword, re.compile(rf"\b{re.escape(keyword)}\b")
        )
        return bool(pattern.search(haystack))
    return keyword in haystack


def prefilter_skip_reason(job: Job) -> str | None:
    """Cheap, keyword-only check that runs before any LLM call. Returns a
    human-readable skip reason if this job is obviously out of scope, or
    None if it should proceed to the LLM as normal. Two independent
    checks, either one can skip:
      1. Title matches an unambiguous non-engineering role keyword.
      2. Neither the title nor the description contains a single
         software/web/mobile-development signal - this doesn't look like
         a tech job at all.
    """
    title_lower = job.title.lower()

    for neg in EXCLUDE_TITLE_KEYWORDS:
        if _keyword_in(neg, title_lower):
            return f"Pre-filter: title matched non-engineering keyword '{neg}'"

    haystack = title_lower + " " + strip_html(job.description_html or "").lower()
    if not any(_keyword_in(pos, haystack) for pos in SKILL_KEYWORDS):
        return "Pre-filter: no software/web/mobile development keyword found in title or description"

    return None


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
    skipped_prefilter = 0
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
                skip_reason = prefilter_skip_reason(job)
                if skip_reason is not None:
                    # match_score stays None on purpose - this job was
                    # never actually scored by an LLM, distinct from a
                    # real score of 0. Status change alone is enough to
                    # remove it from future runs' query.
                    job.status = JobStatus.TRASHED.value
                    job.rationale = skip_reason
                    session.commit()
                    skipped_prefilter += 1
                    log.info("%-40s %s", job.title[:40], skip_reason)
                    continue  # no LLM call made - skip the rate-limit sleep too

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
                continue

            time.sleep(settings.eval_request_delay_seconds)
    finally:
        session.close()

    log.info(
        "Done. %d evaluated, %d approved, %d queued for review, %d skipped by "
        "pre-filter, %d failed.",
        evaluated, approved, queued_for_review, skipped_prefilter, failed,
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
from __future__ import annotations

import logging
import time

from sqlalchemy import select

from app.auth import get_or_create_owner
from app.config import settings
from app.db.models import Job, JobStatus
from app.db.session import get_session, init_db
from app.sources.ashby import AshbySource
from app.sources.base import JobSource, RawJob
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.workday import WorkdaySource

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("hunter")

# Each configured source paired with the company slugs to poll on it.
SOURCE_COMPANIES: list[tuple[JobSource, list[str]]] = [
    (GreenhouseSource(), settings.greenhouse_companies),
    (LeverSource(), settings.lever_companies),
    (AshbySource(), settings.ashby_companies),
    (WorkdaySource(), settings.workday_companies),
]


def upsert_job(session, raw: RawJob, owner_id: int) -> bool:
    """Insert a new job, or update a changed one. Returns True if it was new."""
    existing = session.scalar(
        select(Job).where(Job.source == raw.source, Job.external_id == raw.external_id)
    )
    if existing is None:
        session.add(
            Job(
                user_id=owner_id,
                source=raw.source,
                external_id=raw.external_id,
                title=raw.title,
                company=raw.company,
                location=raw.location,
                description_html=raw.description_html,
                apply_url=raw.apply_url,
                posted_at=raw.posted_at,
                status=JobStatus.PENDING_EVALUATION.value,
            )
        )
        return True

    # Job still exists on the source - refresh fields that can legitimately
    # change (title edits, reposted content) without touching its status,
    # since that's owned by the Evaluator/Executor phases.
    existing.title = raw.title
    existing.location = raw.location
    existing.description_html = raw.description_html
    existing.apply_url = raw.apply_url
    return False


def run() -> None:
    init_db()
    session = get_session()
    owner = get_or_create_owner(session)

    total_new = 0
    total_seen = 0

    try:
        for source, companies in SOURCE_COMPANIES:
            if not companies:
                continue
            for company in companies:
                try:
                    raw_jobs = source.fetch_jobs(company)
                except Exception as exc:  # noqa: BLE001 - one bad company shouldn't kill the run
                    log.error("Failed fetching %s/%s: %s", source.name, company, exc)
                    continue

                new_count = 0
                for raw in raw_jobs:
                    if upsert_job(session, raw, owner.id):
                        new_count += 1
                session.commit()

                total_seen += len(raw_jobs)
                total_new += new_count
                log.info(
                    "%-10s %-20s %3d seen, %3d new",
                    source.name, company, len(raw_jobs), new_count,
                )

                time.sleep(settings.request_delay_seconds)
    finally:
        session.close()

    log.info("Done. %d jobs seen, %d newly inserted as PENDING_EVALUATION.", total_seen, total_new)


if __name__ == "__main__":
    run()

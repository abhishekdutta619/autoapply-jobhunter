from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app.db.models import Job, JobStatus
from app.db.session import get_session


def status_counts(session) -> dict[str, int]:
    rows = session.execute(
        select(Job.status, func.count(Job.id)).group_by(Job.status)
    ).all()
    return dict(rows)


def recent_jobs(session, status: str | None = None, limit: int = 20) -> list[Job]:
    stmt = select(Job).order_by(Job.scraped_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Job.status == status)
    return list(session.scalars(stmt).all())


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect jobs currently in the database.")
    parser.add_argument(
        "--status", choices=[s.value for s in JobStatus], help="Only show this status"
    )
    parser.add_argument("--limit", type=int, default=20, help="Max jobs to list (default 20)")
    args = parser.parse_args()

    session = get_session()
    try:
        counts = status_counts(session)
        total = sum(counts.values())

        print(f"=== {total} job(s) total, by status ===")
        for status in JobStatus:
            print(f"  {status.value:<22} {counts.get(status.value, 0)}")
        print()

        jobs = recent_jobs(session, status=args.status, limit=args.limit)
        label = args.status or "all statuses"
        print(f"=== Most recent {len(jobs)} job(s) ({label}) ===")
        for job in jobs:
            score = f"score={job.match_score}" if job.match_score is not None else "score=--"
            print(
                f"  [{job.status:<20}] {score:<10} {job.source:<10} "
                f"{job.company:<15} {job.title[:50]}"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()

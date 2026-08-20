from __future__ import annotations

import argparse

from app.db.models import Job, JobStatus
from app.db.session import get_session, init_db


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually set a job's status (e.g. you applied outside the tool)."
    )
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--status", required=True, choices=[s.value for s in JobStatus])
    args = parser.parse_args()

    init_db()
    session = get_session()
    try:
        job = session.get(Job, args.job_id)
        if job is None:
            print(f"No job with id={args.job_id}")
            return
        old_status = job.status
        job.status = args.status
        session.commit()
        print(f"Job {job.id} ({job.title}): {old_status} -> {job.status}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

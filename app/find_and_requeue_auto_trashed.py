"""
Finds jobs that were auto-trashed by MAX_EVAL_FAILURES (evaluator.py's
_record_failure_and_maybe_give_up), as opposed to jobs TRASHED for a real
low match score or pre-filter reject. Lets you inspect them, and
optionally requeue them back to PENDING_EVALUATION once the underlying
failure (e.g. the Gemini 402) is actually fixed.

Usage:
    python find_and_requeue_auto_trashed.py                 # just list them
    python find_and_requeue_auto_trashed.py --requeue        # list AND requeue all of them
    python find_and_requeue_auto_trashed.py --requeue --contains "402"  # only requeue ones whose
                                                                          # last error mentions "402"
"""
from __future__ import annotations

import argparse

from app.db.session import get_session
from app.db.models import Job, JobStatus


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requeue", action="store_true", help="Actually requeue matches to PENDING_EVALUATION")
    parser.add_argument("--contains", default=None, help="Only match jobs whose rationale contains this substring")
    args = parser.parse_args()

    session = get_session()
    query = session.query(Job).filter(
        Job.status == JobStatus.TRASHED.value,
        Job.rationale.like("[AUTO-TRASHED: failed evaluation%"),
    )
    if args.contains:
        query = query.filter(Job.rationale.like(f"%{args.contains}%"))

    jobs = query.order_by(Job.id.desc()).all()

    if not jobs:
        print("No auto-trashed jobs found matching that filter.")
        return

    print(f"Found {len(jobs)} auto-trashed job(s):\n")
    for j in jobs:
        print(f"  id={j.id:<8} score={j.match_score}  {j.title[:60]}")
        print(f"      {j.rationale}")
        print()

    if args.requeue:
        confirm = input(f"Requeue all {len(jobs)} of these to PENDING_EVALUATION? [y/N] ").strip().lower()
        if confirm == "y":
            for j in jobs:
                j.status = JobStatus.PENDING_EVALUATION.value
                j.rationale = None
                j.match_score = None
            session.commit()
            print(f"Requeued {len(jobs)} job(s).")
        else:
            print("Not requeued.")


if __name__ == "__main__":
    main()

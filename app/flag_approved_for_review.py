"""One-off remediation script - not part of the regular pipeline.

Moves every currently APPROVED_FOR_APPLY job back to PENDING_EVALUATION
so it surfaces in the dashboard's review queue, following the discovery
that qwen3:4b (via HybridEvaluator, local-only path for any score >85 -
these jobs never got a Gemini cross-check) produces confidently wrong,
self-contradicting scores: reasoning that states a disqualifying gap
outright and then scores 100 anyway (see job id=160's raw leaked
chain-of-thought - "Wait, no - this is a problem" - still scored 100).

Does NOT re-score anything through the LLM - temperature=0 means feeding
the same prompt through the same still-unfixed setup would very likely
just reproduce the same wrong score. This only changes `status`, so a
human decides via the dashboard instead.

Original match_score/rationale are preserved untouched, so you can still
see exactly what qwen3:4b said and why it was wrong - only a prefix is
added to rationale so these are visually distinguishable in the review
queue from jobs that landed there normally via the 73-85 band.

Usage:
    python flag_approved_for_review.py            # dry run - prints what would change
    python flag_approved_for_review.py --apply    # actually applies the change
"""
from __future__ import annotations

import argparse

from app.db.session import get_session, init_db
from app.db.models import Job, JobStatus

FLAG_PREFIX = "[RE-REVIEW: originally auto-approved by qwen3:4b before a scoring reliability bug was found] "


def main(apply: bool) -> None:
    init_db()
    session = get_session()
    try:
        approved = session.query(Job).filter(
            Job.status == JobStatus.APPROVED_FOR_APPLY.value
        ).order_by(Job.match_score.desc()).all()

        if not approved:
            print("No APPROVED_FOR_APPLY jobs found. Nothing to do.")
            return

        print(
            f"{'Would flag' if not apply else 'Flagging'} {len(approved)} job(s) for re-review:\n")
        for job in approved:
            print(
                f"  id={job.id:<6} score={job.match_score:<4} {job.title[:60]}")
            if apply:
                job.status = JobStatus.PENDING_EVALUATION.value
                # Idempotent: don't double-prefix if this script is run twice.
                if not (job.rationale or "").startswith(FLAG_PREFIX):
                    job.rationale = FLAG_PREFIX + (job.rationale or "")

        if apply:
            session.commit()
            print(
                f"\nDone. {len(approved)} job(s) moved to PENDING_EVALUATION for manual review.")
        else:
            print(
                f"\nDry run only - no changes made. Re-run with --apply to actually flag these {len(approved)} job(s).")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flag all APPROVED_FOR_APPLY jobs for manual re-review, "
        "following a discovered qwen3:4b scoring reliability bug."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually apply the change. Without this flag, only prints what would happen.",
    )
    args = parser.parse_args()
    main(apply=args.apply)

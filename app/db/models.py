from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobStatus(str, Enum):
    """Lifecycle a scraped job moves through, per the project's Phase 1-3 design."""

    PENDING_EVALUATION = "PENDING_EVALUATION"
    APPROVED_FOR_APPLY = "APPROVED_FOR_APPLY"
    TRASHED = "TRASHED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """An account that can log into the dashboard via Google or GitHub.

    Identity is keyed on email, not (provider, provider_id) - logging in
    with Google today and GitHub tomorrow using the same email address is
    treated as the same person, on purpose (see app/auth.py). Whoever's
    email matches OWNER_EMAIL is the one account that scraped/evaluated
    jobs ever get attributed to; everyone else gets a real account but a
    genuinely empty dashboard, since nothing else ever creates a Job row
    under their user_id.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Whichever provider they most recently logged in with - purely
    # informational (e.g. for a "signed in with Google" label somewhere);
    # email is what actually identifies the account, not this.
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<User {self.email!r} owner={self.is_owner}>"


class Job(Base):
    """A single job posting pulled from any ATS source."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Whose dashboard this job belongs to. Nullable because rows created
    # before this column existed need a one-time backfill (see
    # db/session.py's _backfill_owner_on_jobs) rather than failing to load
    # - every *new* job always gets one at insert time (see app/hunter.py).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    # Where this job came from and its ID within that system. The combination
    # is what we de-duplicate on, since the same job could theoretically
    # exist across sources but never twice within one.
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(128))

    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(256), index=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str] = mapped_column(String(1024))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), default=JobStatus.PENDING_EVALUATION.value, index=True
    )
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The LLM's reasoning for match_score - previously computed by the
    # Evaluator but discarded; needed by the dashboard's review queue so
    # a human has something to go on besides a bare number.
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Job {self.source}:{self.external_id} {self.title!r} [{self.status}]>"

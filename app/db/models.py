from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
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


class Job(Base):
    """A single job posting pulled from any ATS source."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

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

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Job {self.source}:{self.external_id} {self.title!r} [{self.status}]>"

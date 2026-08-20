from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class RawJob(BaseModel):
    """Normalized shape every adapter converts its source's response into.

    Downstream code (DB writer, Evaluator, Executor) only ever sees this
    shape, so adding a new source never requires touching Phase 2 or 3.
    """

    source: str
    external_id: str
    title: str
    company: str
    location: str | None = None
    description_html: str | None = None
    apply_url: str
    posted_at: datetime | None = None


class JobSource(Protocol):
    """Every ATS adapter (Greenhouse, Lever, Ashby, Workday, ...) implements this."""

    name: str

    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        """Return every currently-listed job for one company on this source."""
        ...

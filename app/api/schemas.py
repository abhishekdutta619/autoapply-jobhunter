from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.db.models import JobStatus


class CamelModel(BaseModel):
    """Base for any schema returned to the Angular frontend. SQLAlchemy/
    Python use snake_case; the dashboard's TypeScript models
    (core/models/job.model.ts) use camelCase - this generates the alias
    automatically instead of hand-writing Field(alias=...) on every field."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class JobOut(CamelModel):
    id: int
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    apply_url: str
    posted_at: datetime | None
    status: JobStatus
    match_score: int | None
    rationale: str | None
    scraped_at: datetime
    updated_at: datetime


class JobStatusUpdate(BaseModel):
    """Body for PATCH /api/jobs/{id}/status - matches JobApiService.approve()
    / .reject() in the Angular client, which both PATCH a bare {status}."""

    status: JobStatus

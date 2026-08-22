from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import JobOut, JobStatusUpdate
from app.db.models import Job, JobStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(status: JobStatus | None = None, db: Session = Depends(get_db)) -> list[Job]:
    query = select(Job).order_by(Job.scraped_at.desc())
    if status is not None:
        query = query.where(Job.status == status.value)
    return list(db.scalars(query).all())


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}")
    return job


@router.patch("/{job_id}/status", response_model=JobOut)
def update_job_status(job_id: int, body: JobStatusUpdate, db: Session = Depends(get_db)) -> Job:
    """Backs the dashboard's approve/reject buttons (JobReviewCardComponent
    -> PipelineStore.approve()/.reject() -> JobApiService.approve()/.reject(),
    both of which PATCH this exact shape)."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}")
    job.status = body.status.value
    db.commit()
    db.refresh(job)
    return job

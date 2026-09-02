from __future__ import annotations

import hashlib
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.sources._retry import RETRY_TRANSIENT_ONLY
from app.sources.base import RawJob

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _external_id(item: dict) -> str:
    # Ashby's public posting-api response doesn't include a bare numeric/UUID
    # `id` field (see developers.ashbyhq.com/docs/public-job-posting-api) -
    # jobUrl is unique per posting, so we key on that. Fall back to a hash
    # of title+jobUrl if jobUrl is ever missing.
    job_url = item.get("jobUrl")
    if job_url:
        return job_url.rstrip("/").rsplit("/", 1)[-1]
    raw = f"{item.get('title', '')}|{item.get('jobUrl', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class AshbySource:
    """https://developers.ashbyhq.com/docs/public-job-posting-api

    No auth required. board_name is the slug in jobs.ashbyhq.com/{board_name}.
    """

    name = "ashby"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=RETRY_TRANSIENT_ONLY,
    )
    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        url = BASE_URL.format(board_name=company_slug)
        response = httpx.get(url, params={"includeCompensation": "false"}, timeout=20.0)
        response.raise_for_status()
        payload = response.json()

        jobs: list[RawJob] = []
        for item in payload.get("jobs", []):
            if not item.get("isListed", True):
                continue
            jobs.append(
                RawJob(
                    source=self.name,
                    external_id=_external_id(item),
                    title=item.get("title", ""),
                    company=company_slug,
                    location=item.get("location"),
                    description_html=item.get("descriptionHtml") or item.get("descriptionPlain"),
                    apply_url=item.get("applyUrl") or item.get("jobUrl", ""),
                    posted_at=_parse_dt(item.get("publishedAt")),
                )
            )
        return jobs

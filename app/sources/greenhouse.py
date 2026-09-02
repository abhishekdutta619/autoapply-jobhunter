from __future__ import annotations

from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.sources._retry import RETRY_TRANSIENT_ONLY
from app.sources.base import RawJob

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GreenhouseSource:
    """https://developers.greenhouse.io/job-board.html

    No auth required for GET endpoints; job board data is public.
    board_token is the slug in boards.greenhouse.io/{token}.
    """

    name = "greenhouse"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=RETRY_TRANSIENT_ONLY,
    )
    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        url = BASE_URL.format(token=company_slug)
        response = httpx.get(url, params={"content": "true"}, timeout=20.0)
        response.raise_for_status()
        payload = response.json()

        jobs: list[RawJob] = []
        for item in payload.get("jobs", []):
            jobs.append(
                RawJob(
                    source=self.name,
                    external_id=str(item["id"]),
                    title=item.get("title", ""),
                    company=company_slug,
                    location=(item.get("location") or {}).get("name"),
                    description_html=item.get("content"),
                    apply_url=item.get("absolute_url", ""),
                    posted_at=_parse_dt(item.get("updated_at")),
                )
            )
        return jobs

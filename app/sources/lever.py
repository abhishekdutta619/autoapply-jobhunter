from __future__ import annotations

from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.sources.base import RawJob

BASE_URL = "https://api.lever.co/v0/postings/{company}"


def _parse_ms_epoch(value: int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


class LeverSource:
    """https://github.com/lever/postings-api

    No auth required; ?mode=json returns published postings only.
    company slug is the segment in jobs.lever.co/{company}.
    """

    name = "lever"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        url = BASE_URL.format(company=company_slug)
        response = httpx.get(url, params={"mode": "json"}, timeout=20.0)
        response.raise_for_status()
        payload = response.json()

        jobs: list[RawJob] = []
        for item in payload:
            jobs.append(
                RawJob(
                    source=self.name,
                    external_id=str(item["id"]),
                    title=item.get("text", ""),
                    company=company_slug,
                    location=(item.get("categories") or {}).get("location"),
                    description_html=item.get("description") or item.get("descriptionPlain"),
                    apply_url=item.get("applyUrl") or item.get("hostedUrl", ""),
                    posted_at=_parse_ms_epoch(item.get("createdAt")),
                )
            )
        return jobs

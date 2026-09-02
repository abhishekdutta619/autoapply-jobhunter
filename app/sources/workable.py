from __future__ import annotations

from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.sources.base import RawJob

# The same public endpoint Workable's own embeddable careers widget calls
# on customers' career pages, so it's stable and unlikely to disappear -
# not an unofficial/reverse-engineered one. No auth required. account_slug
# is the segment in apply.workable.com/{slug}.
BASE_URL = "https://apply.workable.com/api/v1/widget/accounts/{account}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class WorkableSource:
    """https://apply.workable.com/api/v1/widget/accounts/{account}?details=true

    Unlike SmartRecruiters/Workday, `details=true` returns the full job
    description in this single call - no per-job follow-up request or
    extra delay setting needed here.
    """

    name = "workable"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        url = BASE_URL.format(account=company_slug)
        response = httpx.get(url, params={"details": "true"}, timeout=20.0)
        response.raise_for_status()
        payload = response.json()

        jobs: list[RawJob] = []
        for item in payload.get("jobs", []):
            if item.get("state") not in (None, "published"):
                continue
            jobs.append(
                RawJob(
                    source=self.name,
                    external_id=item.get("shortcode") or str(item.get("id", "")),
                    title=item.get("title", ""),
                    company=company_slug,
                    location=(item.get("location") or {}).get("location_str"),
                    description_html=item.get("description") or item.get("full_description"),
                    apply_url=item.get("shortlink") or item.get("url", ""),
                    posted_at=_parse_dt(item.get("published_on") or item.get("created_at")),
                )
            )
        return jobs

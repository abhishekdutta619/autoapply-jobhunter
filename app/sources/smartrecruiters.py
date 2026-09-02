from __future__ import annotations

import time
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sources._retry import RETRY_TRANSIENT_ONLY
from app.sources.base import RawJob

# https://developers.smartrecruiters.com/docs/overview - public, unauthenticated
# Posting API. company_slug is the identifier in jobs.smartrecruiters.com/{slug}
# (also the companyIdentifier path segment used below).
LIST_URL = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting_id}"

PAGE_SIZE = 100
MAX_PAGES = 50  # safety cap: 50 * 100 = 5,000 postings per company per run

# jobAd.sections keys, in a sensible reading order - iterating a dict's own
# key order would work most of the time, but isn't a documented guarantee
# of the API, so this is spelled out explicitly instead.
SECTION_ORDER = ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _location_str(location: dict) -> str | None:
    parts = [location.get("city"), location.get("region"), location.get("country")]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def _description_from_sections(job_ad: dict) -> str | None:
    sections = job_ad.get("sections") or {}
    parts = [
        sections[key]["text"]
        for key in SECTION_ORDER
        if isinstance(sections.get(key), dict) and sections[key].get("text")
    ]
    return "\n\n".join(parts) or None


class SmartRecruitersSource:
    """https://developers.smartrecruiters.com/docs/overview

    No auth required. Unlike Greenhouse/Lever/Ashby, the list endpoint
    doesn't include the job description - only the per-posting detail
    endpoint does (jobAd.sections.*). That means one extra request per
    job to get real description text, same trade-off as Workday - so
    this mirrors that adapter's pattern (toggleable, delayed, and a
    failed detail fetch degrades to a missing description rather than
    dropping the listing or failing the whole company).
    """

    name = "smartrecruiters"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=RETRY_TRANSIENT_ONLY,
    )
    def _fetch_page(self, company_slug: str, offset: int) -> dict:
        url = LIST_URL.format(company=company_slug)
        response = httpx.get(url, params={"offset": offset, "limit": PAGE_SIZE}, timeout=20.0)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=RETRY_TRANSIENT_ONLY,
    )
    def _fetch_description(self, company_slug: str, posting_id: str) -> str | None:
        url = DETAIL_URL.format(company=company_slug, posting_id=posting_id)
        response = httpx.get(url, timeout=20.0)
        response.raise_for_status()
        return _description_from_sections(response.json().get("jobAd") or {})

    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        postings: list[dict] = []
        offset = 0

        for _ in range(MAX_PAGES):
            page = self._fetch_page(company_slug, offset)
            content = page.get("content", [])
            postings.extend(content)

            offset += len(content)
            if not content or offset >= page.get("totalFound", 0):
                break
            time.sleep(settings.request_delay_seconds)

        return [self._to_raw_job(company_slug, item) for item in postings]

    def _to_raw_job(self, company_slug: str, item: dict) -> RawJob:
        posting_id = item.get("id")

        description = None
        if settings.smartrecruiters_fetch_descriptions and posting_id:
            try:
                description = self._fetch_description(company_slug, posting_id)
            except Exception:
                # A single posting's detail request failing shouldn't drop
                # the listing or take the rest of this company's postings
                # down with it - just leave its description empty.
                description = None
            time.sleep(settings.smartrecruiters_detail_delay_seconds)

        return RawJob(
            source=self.name,
            external_id=str(posting_id or item.get("uuid", "")),
            title=item.get("title", ""),
            company=company_slug,
            location=_location_str(item.get("location") or {}),
            description_html=description,
            apply_url=item.get("applyUrl", ""),
            posted_at=_parse_dt(item.get("releasedDate")),
        )

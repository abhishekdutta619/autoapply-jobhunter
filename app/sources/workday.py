from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sources.base import RawJob

# Workday has no documented public API. Career sites are single-page apps
# that call an internal JSON endpoint (the "CXS" system) to render the same
# page you're already allowed to view - so this is public data, just
# fetched directly instead of parsed out of rendered HTML. That's a
# materially different situation from scraping a platform whose terms
# expressly forbid it (e.g. LinkedIn) - but it's real, tenant-specific
# engineering, not a drop-in adapter like Greenhouse/Lever/Ashby:
#
#   - wd_host varies per tenant with no fixed rule (wd1, wd3, wd5, wd12...)
#   - Full descriptions need a SECOND request per job (see fetch_jobs)
#   - Many tenants run Akamai bot management, so this adapter is
#     deliberately slower and more conservative than the other three

LIST_URL = "https://{tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
DETAIL_URL = "https://{tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job{external_path}"
PUBLIC_JOB_URL = "https://{tenant}.{wd_host}.myworkdayjobs.com/en-US/{site}{external_path}"

PAGE_SIZE = 20  # Workday's public list endpoint hard-caps at 20 regardless of what's requested
MAX_PAGES = 250  # safety cap: 250 * 20 = 5,000 jobs per company per run


@dataclass(frozen=True)
class WorkdayCompany:
    tenant: str
    wd_host: str
    site: str


def parse_company_slug(slug: str) -> WorkdayCompany:
    """Workday needs three pieces, not one slug like the other sources.

    WORKDAY_COMPANIES entries look like 'tenant|wd_host|site', e.g.
    'nvidia|wd5|NVIDIAExternalCareerSite'. Find these by opening the
    company's actual careers page and reading them off the URL:
    https://{tenant}.{wd_host}.myworkdayjobs.com/{site}
    """
    parts = [p.strip() for p in slug.split("|")]
    if len(parts) != 3 or not all(parts):
        raise ValueError(
            f"Workday company entry must be 'tenant|wd_host|site', got {slug!r}. "
            "See WORKDAY_COMPANIES in .env.example."
        )
    tenant, wd_host, site = parts
    return WorkdayCompany(tenant=tenant, wd_host=wd_host, site=site)


class WorkdaySource:
    name = "workday"

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=4, max=60))
    def _post_list_page(self, company: WorkdayCompany, offset: int) -> dict:
        url = LIST_URL.format(tenant=company.tenant, wd_host=company.wd_host, site=company.site)
        response = httpx.post(
            url,
            json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
            headers={"Content-Type": "application/json", "Accept-Language": "en-US"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _fetch_description(self, company: WorkdayCompany, external_path: str) -> str | None:
        url = DETAIL_URL.format(
            tenant=company.tenant, wd_host=company.wd_host, site=company.site,
            external_path=external_path,
        )
        response = httpx.get(url, headers={"Accept-Language": "en-US"}, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return (data.get("jobPostingInfo") or {}).get("jobDescription")

    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        company = parse_company_slug(company_slug)
        raw_postings: list[dict] = []
        offset = 0

        for _ in range(MAX_PAGES):
            page = self._post_list_page(company, offset)
            postings = page.get("jobPostings", [])
            raw_postings.extend(postings)

            offset += PAGE_SIZE
            total = page.get("total", len(raw_postings))
            if not postings or offset >= total:
                break
            time.sleep(settings.request_delay_seconds)

        return [self._to_raw_job(company, item) for item in raw_postings]

    def _to_raw_job(self, company: WorkdayCompany, item: dict) -> RawJob:
        external_path = item.get("externalPath", "")

        description = None
        if settings.workday_fetch_descriptions and external_path:
            try:
                description = self._fetch_description(company, external_path)
            except Exception:
                # A single job's detail request failing shouldn't drop the
                # whole listing - just leave its description empty.
                description = None
            time.sleep(settings.workday_detail_delay_seconds)

        return RawJob(
            source=self.name,
            external_id=external_path or item.get("title", ""),
            title=item.get("title", ""),
            company=company.tenant,
            location=item.get("locationsText"),
            description_html=description,
            apply_url=PUBLIC_JOB_URL.format(
                tenant=company.tenant, wd_host=company.wd_host, site=company.site,
                external_path=external_path,
            ),
            # Workday's list endpoint gives a relative string
            # ("Posted 5 Days Ago"), not a reliably parseable timestamp.
            posted_at=None,
        )

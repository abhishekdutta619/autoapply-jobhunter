from __future__ import annotations

from unittest.mock import patch

import httpx

from app.config import settings
from app.sources.ashby import AshbySource
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.smartrecruiters import SmartRecruitersSource
from app.sources.workable import WorkableSource
from app.sources.workday import WorkdaySource, parse_company_slug

# --- Fixtures below mirror each provider's own documented response shape ---

GREENHOUSE_FIXTURE = {
    "jobs": [
        {
            "id": 4020123,
            "title": "Senior Backend Engineer",
            "updated_at": "2026-07-01T10:00:00-00:00",
            "location": {"name": "Remote - US"},
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/4020123",
            "content": "<p>We are looking for...</p>",
        }
    ]
}

LEVER_FIXTURE = [
    {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "text": "Account Executive",
        "hostedUrl": "https://jobs.lever.co/acme/a1b2c3d4",
        "applyUrl": "https://jobs.lever.co/acme/a1b2c3d4/apply",
        "categories": {"team": "Sales", "location": "London", "commitment": "Full-time"},
        "createdAt": 1740000000000,
        "descriptionPlain": "About the role...",
    }
]

ASHBY_FIXTURE = {
    "apiVersion": "1",
    "jobs": [
        {
            "title": "Product Manager",
            "location": "Houston, TX",
            "isListed": True,
            "isRemote": True,
            "workplaceType": "Remote",
            "descriptionHtml": "<p>Join our team</p>",
            "descriptionPlain": "Join our team",
            "publishedAt": "2021-04-30T16:21:55.393+00:00",
            "employmentType": "FullTime",
            "jobUrl": "https://jobs.ashbyhq.com/acme/example_job",
            "applyUrl": "https://jobs.ashbyhq.com/acme/example/apply",
        }
    ],
}

WORKDAY_LIST_PAGE_FIXTURE = {
    "total": 1,
    "jobPostings": [
        {
            "title": "Senior Backend Engineer",
            # Real-world shape observed in production (NVIDIA's tenant):
            # externalPath already starts with "/job/". A fixture using
            # the OTHER shape ("/Fort-Collins/..." with no /job/ prefix)
            # would NOT have caught the doubled "/job/job/" bug - both
            # shapes need coverage, see the dedicated test below.
            "externalPath": "/job/US-CA-Santa-Clara/Senior-Backend-Engineer_JR2018037",
            "locationsText": "Fort Collins, CO",
            "postedOn": "Posted 5 Days Ago",
            "bulletFields": ["R-3164651"],
            "remoteType": "Hybrid",
            "timeType": "Full time",
        }
    ],
}

WORKDAY_DETAIL_FIXTURE = {
    "jobPostingInfo": {
        "jobDescription": "<p>We are looking for a backend engineer...</p>",
    }
}


def _mock_response(json_body):
    request = httpx.Request("GET", "https://example.invalid")
    return httpx.Response(status_code=200, json=json_body, request=request)


def test_greenhouse_adapter_parses_fixture():
    with patch("httpx.get", return_value=_mock_response(GREENHOUSE_FIXTURE)):
        jobs = GreenhouseSource().fetch_jobs("acme")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "greenhouse"
    assert job.external_id == "4020123"
    assert job.title == "Senior Backend Engineer"
    assert job.location == "Remote - US"
    assert job.apply_url.endswith("/jobs/4020123")
    assert job.posted_at is not None


def test_lever_adapter_parses_fixture():
    with patch("httpx.get", return_value=_mock_response(LEVER_FIXTURE)):
        jobs = LeverSource().fetch_jobs("acme")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "lever"
    assert job.external_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert job.title == "Account Executive"
    assert job.location == "London"
    assert job.apply_url.endswith("/apply")
    assert job.posted_at is not None


def test_ashby_adapter_parses_fixture():
    with patch("httpx.get", return_value=_mock_response(ASHBY_FIXTURE)):
        jobs = AshbySource().fetch_jobs("acme")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "ashby"
    assert job.external_id == "example_job"  # derived from jobUrl slug
    assert job.title == "Product Manager"
    assert job.location == "Houston, TX"
    assert job.posted_at is not None


def test_ashby_adapter_skips_unlisted_jobs():
    fixture = {
        "jobs": [
            {**ASHBY_FIXTURE["jobs"][0], "isListed": False},
        ]
    }
    with patch("httpx.get", return_value=_mock_response(fixture)):
        jobs = AshbySource().fetch_jobs("acme")

    assert jobs == []


def test_parse_company_slug_splits_three_pieces():
    company = parse_company_slug("nvidia|wd5|NVIDIAExternalCareerSite")
    assert company.tenant == "nvidia"
    assert company.wd_host == "wd5"
    assert company.site == "NVIDIAExternalCareerSite"


def test_parse_company_slug_rejects_wrong_shape():
    for bad_slug in ["nvidia", "nvidia|wd5", "nvidia|wd5|site|extra", "||"]:
        try:
            parse_company_slug(bad_slug)
            assert False, f"expected ValueError for {bad_slug!r}"
        except ValueError:
            pass


def test_workday_adapter_parses_fixture_with_description(monkeypatch):
    monkeypatch.setattr(settings, "workday_fetch_descriptions", True)
    monkeypatch.setattr(settings, "workday_detail_delay_seconds", 0)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    with patch("httpx.post", return_value=_mock_response(WORKDAY_LIST_PAGE_FIXTURE)), \
         patch("httpx.get", return_value=_mock_response(WORKDAY_DETAIL_FIXTURE)) as mock_get:
        jobs = WorkdaySource().fetch_jobs("nvidia|wd5|NVIDIAExternalCareerSite")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "workday"
    assert job.title == "Senior Backend Engineer"
    assert job.company == "nvidia"
    assert job.location == "Fort Collins, CO"
    assert job.external_id == "/job/US-CA-Santa-Clara/Senior-Backend-Engineer_JR2018037"
    assert job.apply_url == (
        "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"
        "/job/US-CA-Santa-Clara/Senior-Backend-Engineer_JR2018037"
    )
    assert job.description_html == "<p>We are looking for a backend engineer...</p>"
    assert job.posted_at is None  # relative string, deliberately not parsed

    # Regression test for a real production bug: externalPath that already
    # starts with "/job/" must NOT produce a doubled "/job/job/" detail URL
    # (Workday returns 422 Unprocessable Entity for that, on every job).
    called_url = mock_get.call_args[0][0]
    assert "/job/job/" not in called_url
    assert called_url == (
        "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/"
        "NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Senior-Backend-Engineer_JR2018037"
    )


def test_workday_detail_url_handles_external_path_without_job_prefix(monkeypatch):
    """The other real-world shape: some tenants' externalPath does NOT
    include a leading '/job/'. Confirm the detail URL still comes out
    correct - exactly one '/job' segment - in this case too.
    """
    monkeypatch.setattr(settings, "workday_fetch_descriptions", True)
    monkeypatch.setattr(settings, "workday_detail_delay_seconds", 0)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    fixture = {
        "total": 1,
        "jobPostings": [
            {
                **WORKDAY_LIST_PAGE_FIXTURE["jobPostings"][0],
                "externalPath": "/Fort-Collins/Senior-Backend-Engineer_R-3164651",
            },
        ],
    }

    with patch("httpx.post", return_value=_mock_response(fixture)), \
         patch("httpx.get", return_value=_mock_response(WORKDAY_DETAIL_FIXTURE)) as mock_get:
        WorkdaySource().fetch_jobs("nvidia|wd5|NVIDIAExternalCareerSite")

    called_url = mock_get.call_args[0][0]
    assert called_url == (
        "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/"
        "NVIDIAExternalCareerSite/job/Fort-Collins/Senior-Backend-Engineer_R-3164651"
    )


def test_workday_adapter_skips_description_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "workday_fetch_descriptions", False)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    with patch("httpx.post", return_value=_mock_response(WORKDAY_LIST_PAGE_FIXTURE)) as mock_post, \
         patch("httpx.get") as mock_get:
        jobs = WorkdaySource().fetch_jobs("nvidia|wd5|NVIDIAExternalCareerSite")

    assert jobs[0].description_html is None
    mock_get.assert_not_called()  # no detail request made at all
    assert mock_post.call_count == 1


def test_workday_adapter_paginates_until_total_reached(monkeypatch):
    monkeypatch.setattr(settings, "workday_fetch_descriptions", False)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    page_one = {
        "total": 25,
        "jobPostings": [
            {**WORKDAY_LIST_PAGE_FIXTURE["jobPostings"][0], "externalPath": f"/job/x{i}"}
            for i in range(20)
        ],
    }
    page_two = {
        "total": 25,
        "jobPostings": [
            {**WORKDAY_LIST_PAGE_FIXTURE["jobPostings"][0], "externalPath": f"/job/x{i}"}
            for i in range(20, 25)
        ],
    }

    with patch(
        "httpx.post",
        side_effect=[_mock_response(page_one), _mock_response(page_two)],
    ) as mock_post:
        jobs = WorkdaySource().fetch_jobs("nvidia|wd5|NVIDIAExternalCareerSite")

    assert len(jobs) == 25
    assert mock_post.call_count == 2  # stopped once offset(40) >= total(25)


def test_workday_adapter_detail_failure_does_not_drop_the_listing(monkeypatch):
    monkeypatch.setattr(settings, "workday_fetch_descriptions", True)
    monkeypatch.setattr(settings, "workday_detail_delay_seconds", 0)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    with patch("httpx.post", return_value=_mock_response(WORKDAY_LIST_PAGE_FIXTURE)), \
         patch("httpx.get", side_effect=httpx.ConnectError("boom")), \
         patch("time.sleep"):  # skip tenacity's real backoff delay in this test
        jobs = WorkdaySource().fetch_jobs("nvidia|wd5|NVIDIAExternalCareerSite")

    assert len(jobs) == 1  # listing survives even though its detail fetch failed
    assert jobs[0].description_html is None

# --- SmartRecruiters ---

SMARTRECRUITERS_POSTING_FIXTURE = {
    "id": "744000137225639",
    "uuid": "dc8980b2-4f93-4556-8944-73612ee741ad",
    "title": "Senior Backend Engineer",
    "location": {"city": "Austin", "region": "TX", "country": "United States"},
    "releasedDate": "2026-07-01T10:00:00.000Z",
    "applyUrl": "https://jobs.smartrecruiters.com/acme/744000137225639?oga=true",
}

SMARTRECRUITERS_DETAIL_FIXTURE = {
    "jobAd": {
        "sections": {
            "jobDescription": {"title": "Job Description", "text": "We are looking for a backend engineer."},
            "qualifications": {"title": "Qualifications", "text": "5+ years of experience."},
        }
    }
}


def _smartrecruiters_list_page(content, offset=0, total=None):
    return {"offset": offset, "limit": 100, "totalFound": total if total is not None else len(content), "content": content}


def test_smartrecruiters_adapter_parses_fixture_with_description(monkeypatch):
    monkeypatch.setattr(settings, "smartrecruiters_fetch_descriptions", True)
    monkeypatch.setattr(settings, "smartrecruiters_detail_delay_seconds", 0)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    list_page = _smartrecruiters_list_page([SMARTRECRUITERS_POSTING_FIXTURE])

    def _handler(url, **kwargs):
        if url.rstrip("/").endswith("/postings"):
            return _mock_response(list_page)
        return _mock_response(SMARTRECRUITERS_DETAIL_FIXTURE)

    with patch("httpx.get", side_effect=_handler):
        jobs = SmartRecruitersSource().fetch_jobs("acme")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "smartrecruiters"
    assert job.external_id == "744000137225639"
    assert job.title == "Senior Backend Engineer"
    assert job.location == "Austin, TX, United States"
    assert job.apply_url.endswith("744000137225639?oga=true")
    assert job.posted_at is not None
    assert job.description_html == "We are looking for a backend engineer.\n\n5+ years of experience."


def test_smartrecruiters_adapter_skips_description_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "smartrecruiters_fetch_descriptions", False)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    list_page = _smartrecruiters_list_page([SMARTRECRUITERS_POSTING_FIXTURE])

    with patch("httpx.get", return_value=_mock_response(list_page)) as mock_get:
        jobs = SmartRecruitersSource().fetch_jobs("acme")

    assert jobs[0].description_html is None
    assert mock_get.call_count == 1  # only the list page - no detail fetch made at all


def test_smartrecruiters_adapter_detail_failure_does_not_drop_the_listing(monkeypatch):
    """Mirrors Workday's equivalent test - a single posting's detail
    request failing shouldn't drop that listing, or take the rest of the
    company's postings down with it."""
    monkeypatch.setattr(settings, "smartrecruiters_fetch_descriptions", True)
    monkeypatch.setattr(settings, "smartrecruiters_detail_delay_seconds", 0)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    list_page = _smartrecruiters_list_page([SMARTRECRUITERS_POSTING_FIXTURE])

    def _handler(url, **kwargs):
        if url.rstrip("/").endswith("/postings"):
            return _mock_response(list_page)
        raise httpx.ConnectError("boom")

    with patch("httpx.get", side_effect=_handler), patch("time.sleep"):
        jobs = SmartRecruitersSource().fetch_jobs("acme")

    assert len(jobs) == 1
    assert jobs[0].description_html is None


def test_smartrecruiters_adapter_paginates_until_total_found_reached(monkeypatch):
    monkeypatch.setattr(settings, "smartrecruiters_fetch_descriptions", False)
    monkeypatch.setattr(settings, "request_delay_seconds", 0)

    page_one = _smartrecruiters_list_page(
        [{**SMARTRECRUITERS_POSTING_FIXTURE, "id": f"job-{i}"} for i in range(100)],
        offset=0, total=150,
    )
    page_two = _smartrecruiters_list_page(
        [{**SMARTRECRUITERS_POSTING_FIXTURE, "id": f"job-{i}"} for i in range(100, 150)],
        offset=100, total=150,
    )

    with patch(
        "httpx.get", side_effect=[_mock_response(page_one), _mock_response(page_two)]
    ) as mock_get:
        jobs = SmartRecruitersSource().fetch_jobs("acme")

    assert len(jobs) == 150
    assert mock_get.call_count == 2  # stopped once offset(150) >= totalFound(150)


# --- Workable ---

WORKABLE_FIXTURE = {
    "name": "Acme Inc",
    "jobs": [
        {
            "id": "3c47ff",
            "title": "Account Executive",
            "shortcode": "AE84C38EE2",
            "state": "published",
            "department": "Sales",
            "location": {"location_str": "London, United Kingdom", "telecommuting": False},
            "shortlink": "https://apply.workable.com/j/AE84C38EE2",
            "url": "https://acme.workable.com/jobs/3949357",
            "published_on": "2026-07-01",
            "description": "<p>We are hiring an Account Executive.</p>",
        }
    ],
}


def test_workable_adapter_parses_fixture():
    with patch("httpx.get", return_value=_mock_response(WORKABLE_FIXTURE)):
        jobs = WorkableSource().fetch_jobs("acme")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "workable"
    assert job.external_id == "AE84C38EE2"
    assert job.title == "Account Executive"
    assert job.location == "London, United Kingdom"
    assert job.apply_url == "https://apply.workable.com/j/AE84C38EE2"
    assert job.description_html == "<p>We are hiring an Account Executive.</p>"
    assert job.posted_at is not None


def test_workable_adapter_skips_unpublished_jobs():
    fixture = {"jobs": [{**WORKABLE_FIXTURE["jobs"][0], "state": "draft"}]}
    with patch("httpx.get", return_value=_mock_response(fixture)):
        jobs = WorkableSource().fetch_jobs("acme")

    assert jobs == []

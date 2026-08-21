from __future__ import annotations

from unittest.mock import patch

import httpx

from app.config import settings
from app.sources.ashby import AshbySource
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
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
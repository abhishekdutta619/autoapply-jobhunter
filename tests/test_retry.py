from __future__ import annotations

import httpx

from app.sources._retry import _is_retryable


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.invalid")
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_permanent_client_errors_are_not_retried():
    # 404: wrong board slug / company isn't on this ATS. 401: tenant needs
    # auth we don't have. 422: usually a wrong Workday site/tenant
    # combination. All three fail identically no matter how many times
    # the exact same request is retried.
    assert _is_retryable(_status_error(404)) is False
    assert _is_retryable(_status_error(401)) is False
    assert _is_retryable(_status_error(422)) is False


def test_rate_limiting_and_bot_challenges_are_retried():
    # 403 is included alongside 429 based on observed behavior in a real
    # run: an isolated detail-page 403 against a Workday/Akamai-fronted
    # site cleared up within seconds, with the very next request
    # succeeding fine - a momentary challenge, not a durable denial.
    assert _is_retryable(_status_error(429)) is True
    assert _is_retryable(_status_error(403)) is True


def test_server_errors_are_retried():
    assert _is_retryable(_status_error(500)) is True
    assert _is_retryable(_status_error(503)) is True


def test_network_level_failures_are_retried():
    request = httpx.Request("GET", "https://example.invalid")
    assert _is_retryable(httpx.ConnectError("boom", request=request)) is True
    assert _is_retryable(httpx.ReadTimeout("boom", request=request)) is True


def test_unrelated_exceptions_are_not_retried():
    assert _is_retryable(ValueError("not an http error")) is False

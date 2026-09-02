from __future__ import annotations

import httpx
from tenacity import retry_if_exception


def _is_retryable(exc: BaseException) -> bool:
    """Whether retrying this exception could plausibly succeed.

    A 404 (wrong board slug, or this company isn't actually on this ATS),
    401 (this tenant requires auth we don't have), and 422 (malformed
    request - usually a wrong site/tenant combination for Workday) are all
    permanent conditions: the 4th identical request fails for exactly the
    same reason as the 1st. Retrying them only burns through the backoff
    schedule for nothing - seen directly in a production run, where ~30
    misconfigured company entries each cost 10-20+ seconds of pointless
    retrying before failing anyway regardless.

    429 (rate limited) and 5xx (server-side issue) are genuinely
    transient, as is - in practice, for these Workday/Akamai-fronted
    sites specifically - 403: also seen directly in production logs,
    where an isolated detail-page 403 cleared up within a few seconds
    and the very next job's request succeeded fine, matching bot-
    management momentarily challenging a request rather than a real,
    durable access denial. Network-level failures (timeout, connection
    reset) round out the retryable set.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status in (403, 429) or status >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


RETRY_TRANSIENT_ONLY = retry_if_exception(_is_retryable)

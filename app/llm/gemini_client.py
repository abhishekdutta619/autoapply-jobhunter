from __future__ import annotations

import json
import logging

import httpx
from google import genai
from google.genai import errors, types
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.llm.base import CloudQuotaExhaustedError, DropdownSelection, EvaluationResult
from app.llm.prompts import (
    ANSWER_SYSTEM_PROMPT,
    DROPDOWN_SYSTEM_PROMPT,
    RESULT_SCHEMA,
    SYSTEM_PROMPT,
    build_answer_prompt,
    build_dropdown_prompt,
    build_dropdown_schema,
    build_user_prompt,
)

log = logging.getLogger("llm.gemini")

REQUEST_TIMEOUT_MS = 60_000

_TRANSIENT_CODES = {429, 503}


def _is_daily_quota_exhausted(exc: errors.APIError) -> bool:
    """Distinguishes a DAILY quota exhaustion from a short-lived 429 rate
    limit - Google returns the identical HTTP 429 / RESOURCE_EXHAUSTED
    status for both. Verified against a real 2026-09-04 error: the
    QuotaFailure detail's quotaId contains "PerDay" for a genuine daily
    exhaustion (GenerateRequestsPerDayPerProjectPerModel-FreeTier)."""
    try:
        detail_entries = exc.details.get("error", {}).get("details", [])
    except AttributeError:
        return False
    for entry in detail_entries:
        if str(entry.get("@type", "")).endswith("QuotaFailure"):
            for violation in entry.get("violations", []):
                if "PerDay" in violation.get("quotaId", ""):
                    return True
    return False


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, CloudQuotaExhaustedError):
        # Won't clear on any retry schedule that fits within a single
        # run - retrying wastes the full budget for nothing. Confirmed:
        # a 2026-09-04 run burned all 4 attempts on 20+ jobs against an
        # already-exhausted quota before giving up on each one anyway.
        return False
    if isinstance(exc, errors.APIError):
        return getattr(exc, "code", None) in _TRANSIENT_CODES
    return isinstance(exc, httpx.TransportError)


class GeminiEvaluator:
    """Uses Gemini's response_json_schema for the same schema-constrained-
    decoding guarantee as the OpenAI/Anthropic/Ollama clients.

    Free tier (Flash-family models) needs no credit card and no paid
    subscription - get a key at https://aistudio.google.com/apikey. A
    consumer "Gemini Pro"/Google AI Pro subscription is a separate, unrelated
    product (chat interface only) and neither grants nor is required for
    this - don't confuse the two when reading Google's docs.

    Model IDs and rate limits both shift over time - gemini-2.5-flash,
    this client's original default, returned a 404 "no longer available to
    new users" within days of being set. If GEMINI_MODEL in .env starts
    404ing, check https://ai.dev/rate-limit (shown in the API's own error
    responses) for your project's current available models rather than
    trusting a specific model name to stay valid indefinitely.

    Some Gemini models (2.5+) include an internal reasoning trace by
    default (similar in spirit to the qwen3:4b thinking-mode issue found
    earlier), but this runs on Google's infrastructure rather than local
    CPU, so it doesn't carry the same practical cost. If you profile this
    against real usage and it matters, GenerateContentConfig also accepts
    a `thinking_config=types.ThinkingConfig(thinking_budget=0)` to disable
    it explicitly - left out here to keep the implementation minimal.
    """

    def __init__(self, api_key: str, model: str = "gemini-3.7-flash") -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Get a free one (no credit card, "
                "no subscription needed) at https://aistudio.google.com/apikey "
                "and add it to your .env file."
            )
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
        self._model = model

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=5, max=60),
        reraise=True,
    )
    def _generate(self, contents: str, config: types.GenerateContentConfig):
        try:
            return self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except errors.ClientError as exc:
            if getattr(exc, "code", None) == 429 and _is_daily_quota_exhausted(exc):
                raise CloudQuotaExhaustedError(
                    f"Gemini daily free-tier request quota exhausted for "
                    f"model {self._model!r}. Original: {exc.message}"
                ) from exc
            if getattr(exc, "code", None) == 404:
                raise errors.ClientError(
                    exc.code,
                    {
                        "error": {
                            "message": (
                                f"{exc.message} (GEMINI_MODEL={self._model!r} in your .env - "
                                "check https://ai.dev/rate-limit for currently available "
                                "models on your project if this model has been retired)"
                            )
                        }
                    },
                    exc.response,
                ) from exc
            raise

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        response = self._generate(
            contents=build_user_prompt(resume, job_title, job_description),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=RESULT_SCHEMA,
                temperature=0,
            ),
        )
        data = json.loads(response.text)
        return EvaluationResult(**data)

    def draft_answer(
        self,
        question: str,
        story_title: str,
        story_text: str,
        job_title: str,
        job_description: str,
    ) -> str:
        response = self._generate(
            contents=build_answer_prompt(
                question, story_title, story_text, job_title, job_description
            ),
            config=types.GenerateContentConfig(system_instruction=ANSWER_SYSTEM_PROMPT),
        )
        return response.text.strip()

    def select_dropdown_option(
        self, question: str, options: list[str], candidate_context: str
    ) -> DropdownSelection:
        response = self._generate(
            contents=build_dropdown_prompt(question, options, candidate_context),
            config=types.GenerateContentConfig(
                system_instruction=DROPDOWN_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=build_dropdown_schema(options),
                temperature=0,
            ),
        )
        data = json.loads(response.text)
        return DropdownSelection(**data)
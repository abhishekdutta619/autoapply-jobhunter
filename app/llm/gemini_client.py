from __future__ import annotations

import json
import logging

import httpx
from google import genai
from google.genai import errors, types
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.llm.base import DropdownSelection, EvaluationResult
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

# Confirmed against a real run: WinError 10053 (connection aborted by the
# host) surfaced as an httpx.TransportError, not a google.genai.errors
# .APIError - so it wasn't retried at all, and with no request timeout
# configured (the SDK's default is unbounded), that single hung
# connection took ~20 minutes to finally fail. Both gaps fixed here:
# network-level errors are now retried too, and REQUEST_TIMEOUT_MS caps
# how long any one attempt can hang before tenacity moves on to a retry.
REQUEST_TIMEOUT_MS = 60_000  # 60s - generous for a Flash-class classification call, not 20 minutes

# 429 (quota exceeded) and 503 (server overloaded) are both transient -
# worth retrying with backoff. Everything else (404 wrong model name, 400
# bad request, 403 bad key) is permanent - retrying just wastes time and
# delays the actual error. Confirmed against a real run: free-tier quota
# for gemini-3.7-flash was measured at exactly 5 requests/minute for this
# project - published rate-limit numbers online are unreliable and
# conflict with each other (5/10/15/30 RPM depending on source and date),
# so this retries on the *symptom* (429/503) rather than trying to compute
# a "safe" delay from a number that isn't stable enough to trust.
_TRANSIENT_CODES = {429, 503}


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, errors.APIError):
        return getattr(exc, "code", None) in _TRANSIENT_CODES
    # Connection drops, read timeouts, protocol errors - confirmed real
    # (WinError 10053 on Windows), not hypothetical. Always worth a retry;
    # there's no permanent-vs-transient distinction to make here the way
    # there is for HTTP status codes.
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
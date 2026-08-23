from __future__ import annotations

import json

from google import genai
from google.genai import types

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


class GeminiEvaluator:
    """Uses Gemini's response_json_schema for the same schema-constrained-
    decoding guarantee as the OpenAI/Anthropic/Ollama clients.

    Free tier (Flash-family models) needs no credit card and no paid
    subscription - get a key at https://aistudio.google.com/apikey. A
    consumer "Gemini Pro"/Google AI Pro subscription is a separate, unrelated
    product (chat interface only) and neither grants nor is required for
    this - don't confuse the two when reading Google's docs.

    Some Gemini models (2.5+) include an internal reasoning trace by
    default (similar in spirit to the qwen3:4b thinking-mode issue found
    this session), but this runs on Google's infrastructure rather than
    local CPU, so it doesn't carry the same practical cost - free-tier
    Flash-class calls should still land in the 1-5s range, not 30-100s+.
    If you profile this against real usage and it matters, GenerateContentConfig
    also accepts a `thinking_config=types.ThinkingConfig(thinking_budget=0)`
    to disable it explicitly - left out here to keep the initial
    implementation minimal; add it if real usage shows it's needed.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Get a free one (no credit card, "
                "no subscription needed) at https://aistudio.google.com/apikey "
                "and add it to your .env file."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        response = self._client.models.generate_content(
            model=self._model,
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
        response = self._client.models.generate_content(
            model=self._model,
            contents=build_answer_prompt(
                question, story_title, story_text, job_title, job_description
            ),
            config=types.GenerateContentConfig(system_instruction=ANSWER_SYSTEM_PROMPT),
        )
        return response.text.strip()

    def select_dropdown_option(
        self, question: str, options: list[str], candidate_context: str
    ) -> DropdownSelection:
        response = self._client.models.generate_content(
            model=self._model,
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
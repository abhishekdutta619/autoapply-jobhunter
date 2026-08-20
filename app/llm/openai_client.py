from __future__ import annotations

import json

from openai import OpenAI

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


class OpenAIEvaluator:
    """Uses Chat Completions structured outputs to force valid JSON back.

    https://platform.openai.com/docs/guides/structured-outputs
    """

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to your .env file."
            )
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(resume, job_title, job_description)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "job_match_evaluation",
                    "schema": RESULT_SCHEMA,
                    "strict": True,
                },
            },
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return EvaluationResult(**data)

    def draft_answer(
        self,
        question: str,
        story_title: str,
        story_text: str,
        job_title: str,
        job_description: str,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_answer_prompt(
                        question, story_title, story_text, job_title, job_description
                    ),
                },
            ],
        )
        return response.choices[0].message.content.strip()

    def select_dropdown_option(
        self, question: str, options: list[str], candidate_context: str
    ) -> DropdownSelection:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": DROPDOWN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_dropdown_prompt(question, options, candidate_context),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "dropdown_selection",
                    "schema": build_dropdown_schema(options),
                    "strict": True,
                },
            },
        )
        data = json.loads(response.choices[0].message.content)
        return DropdownSelection(**data)

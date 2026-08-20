from __future__ import annotations

from anthropic import Anthropic

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

TOOL_NAME = "submit_evaluation"


class AnthropicEvaluator:
    """Uses forced tool_choice to guarantee a structured response back.

    https://docs.claude.com/en/docs/build-with-claude/tool-use
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(resume, job_title, job_description)},
            ],
            tools=[
                {
                    "name": TOOL_NAME,
                    "description": "Submit the resume-to-job match evaluation.",
                    "input_schema": RESULT_SCHEMA,
                }
            ],
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )
        tool_use_block = next(
            block for block in response.content if block.type == "tool_use"
        )
        return EvaluationResult(**tool_use_block.input)

    def draft_answer(
        self,
        question: str,
        story_title: str,
        story_text: str,
        job_title: str,
        job_description: str,
    ) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=ANSWER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_answer_prompt(
                        question, story_title, story_text, job_title, job_description
                    ),
                },
            ],
        )
        text_block = next(block for block in response.content if block.type == "text")
        return text_block.text.strip()

    def select_dropdown_option(
        self, question: str, options: list[str], candidate_context: str
    ) -> DropdownSelection:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            system=DROPDOWN_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_dropdown_prompt(question, options, candidate_context),
                },
            ],
            tools=[
                {
                    "name": "select_dropdown_option",
                    "description": "Select the best dropdown option for this question.",
                    "input_schema": build_dropdown_schema(options),
                }
            ],
            tool_choice={"type": "tool", "name": "select_dropdown_option"},
        )
        tool_use_block = next(
            block for block in response.content if block.type == "tool_use"
        )
        return DropdownSelection(**tool_use_block.input)

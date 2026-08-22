from __future__ import annotations

import json

import httpx

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


class OllamaEvaluator:
    """Runs entirely on your own machine via Ollama - no API key, no
    per-request cost. Uses Ollama's native /api/chat endpoint, whose
    `format` field accepts a raw JSON schema and constrains the model's
    decoding to match it (grammar-based, not just prompted) - the same
    guarantee OpenAI's structured outputs and Anthropic's tool_choice give,
    just running locally instead of over the network.

    Tradeoffs versus a cloud provider, worth knowing going in:
    - Meaningfully slower, especially on CPU-only hardware
    - Answer/reasoning quality is generally a step down from GPT-4o or
      Claude for an 8B-class model - review outputs more critically,
      particularly early on
    - format=<schema> guarantees syntactically valid, schema-conformant
      JSON: it does NOT guarantee the *content* is good. DropdownMapper's
      confidence gate and the human review step matter just as much here.

    See README's "Local LLM (Ollama)" section for setup and model
    recommendations for your specific hardware.
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def _chat(self, system_prompt: str, user_prompt: str, schema: dict | None = None) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            # temperature=0 for determinism - Ollama's own docs recommend
            # this for schema-constrained generation specifically.
            "options": {"temperature": 0},
        }
        if schema is not None:
            payload["format"] = schema

        try:
            # Local inference (especially CPU-only) can be genuinely slow -
            # a short cloud-API-style timeout would fail valid, if slow,
            # responses.
            response = httpx.post(
                f"{self._base_url}/api/chat", json=payload, timeout=300.0
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Could not reach Ollama at {self._base_url}. Is it running? "
                "Check the Ollama app/tray icon, or start it with "
                f"'ollama serve'. Also confirm the model is pulled: "
                f"'ollama pull {self._model}'."
            ) from exc

        return response.json()["message"]["content"]

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        content = self._chat(
            SYSTEM_PROMPT,
            build_user_prompt(resume, job_title, job_description),
            schema=RESULT_SCHEMA,
        )
        return EvaluationResult(**json.loads(content))

    def draft_answer(
        self,
        question: str,
        story_title: str,
        story_text: str,
        job_title: str,
        job_description: str,
    ) -> str:
        content = self._chat(
            ANSWER_SYSTEM_PROMPT,
            build_answer_prompt(question, story_title, story_text, job_title, job_description),
        )
        return content.strip()

    def select_dropdown_option(
        self, question: str, options: list[str], candidate_context: str
    ) -> DropdownSelection:
        content = self._chat(
            DROPDOWN_SYSTEM_PROMPT,
            build_dropdown_prompt(question, options, candidate_context),
            schema=build_dropdown_schema(options),
        )
        return DropdownSelection(**json.loads(content))
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """What every LLM provider must return for a resume-vs-job comparison."""

    score: int = Field(ge=1, le=100)
    reasoning: str


class DropdownSelection(BaseModel):
    """What every LLM provider must return for a dropdown-mapping decision."""

    selected_option: str  # one of the provided options verbatim, or "NONE"
    confidence: str  # "high" | "medium" | "low"


class LLMClient(Protocol):
    """Every provider (OpenAI, Anthropic, ...) implements these methods.

    Same idea as JobSource in Phase 1: callers never need to know which
    provider is behind this - they just call the methods and get a
    normalized result back.
    """

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        ...

    def draft_answer(
        self,
        question: str,
        story_title: str,
        story_text: str,
        job_title: str,
        job_description: str,
    ) -> str:
        ...

    def select_dropdown_option(
        self, question: str, options: list[str], candidate_context: str
    ) -> DropdownSelection:
        ...

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class CloudQuotaExhaustedError(Exception):
    """Raised by a cloud LLMClient implementation when its provider
    reports that today's usage quota is exhausted - as opposed to a
    short-lived rate limit that a normal retry-with-backoff can clear.
    Provider-agnostic on purpose (lives here, not in a specific
    provider's client file) so HybridEvaluator and the Evaluator's
    failure handling can recognize it without needing to know which
    cloud provider raised it. A provider that can't distinguish "quota
    exhausted for the day" from "transient rate limit" simply never
    raises this - it's an opt-in signal, not a requirement.

    Motivated by a real 2026-09-04 run where 20+ jobs each burned all 4
    retry attempts against an already-exhausted Gemini free-tier daily
    quota, and where the failure-counter built for job id=223's
    unrelated hangs would otherwise eventually auto-TRASH a possibly
    great match purely because of unlucky timing against an external,
    resets-tomorrow condition that has nothing to do with that job.
    """


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
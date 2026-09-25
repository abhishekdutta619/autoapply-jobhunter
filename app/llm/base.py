from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class NonJobEvaluationError(Exception):
    """Base class for evaluation failures that are NOT specific to the
    job being evaluated - an external/environmental condition (a
    provider unreachable, rate/quota-limited, etc.) rather than anything
    wrong with that job's content. Exempted from the Evaluator's
    MAX_EVAL_FAILURES give-up counter (see
    _record_failure_and_maybe_give_up) - counting these would eventually
    auto-TRASH jobs for reasons that have nothing to do with them and
    that resolve on their own. Subclass this for any new category of
    external failure rather than adding another one-off except clause
    in evaluator.py's loop.
    """


class CloudQuotaExhaustedError(Exception):
    """Raised by a cloud LLMClient implementation when its provider
    reports that today's usage quota is exhausted - as opposed to a
    short-lived rate limit that a normal retry-with-backoff can clear.

    Motivated by a real 2026-09-04 run where 20+ jobs each burned all 4
    retry attempts against an already-exhausted Gemini free-tier daily
    quota, and where the failure-counter built for job id=223's
    unrelated hangs would otherwise eventually auto-TRASH a possibly
    great match purely because of unlucky timing against an external,
    resets-tomorrow condition that has nothing to do with that job.
    """

class ProviderUnavailableError(NonJobEvaluationError):
    """Raised when a provider's server/endpoint can't be reached at all
    (connection refused, DNS failure, etc.) - as opposed to being
    reachable but returning an error for a specific request. Confirmed
    real: a 2026-09-23 run hit this on 12 consecutive jobs because Ollama
    hadn't finished starting yet when the run began - a whole-run,
    environment-level condition present for every job attempted in that
    window, not a defect in any single one of them. Unlike quota
    exhaustion, this is usually transient on the scale of seconds to
    minutes (the process finishing startup), so per-job retry-and-
    continue remains correct here - no run-wide circuit breaker needed,
    just exemption from the strike counter.
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
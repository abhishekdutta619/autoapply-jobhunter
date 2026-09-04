from __future__ import annotations

import logging

from app.llm.base import CloudQuotaExhaustedError, DropdownSelection, EvaluationResult, LLMClient

log = logging.getLogger("llm.hybrid")


class HybridEvaluator:
    """Bulk jobs -> local model -> clear reject (done) or anything else
    (escalate to cloud for a second opinion).

    ... (unchanged docstring content from the trust-local-for-TRASH-only
    version) ...

    Circuit breaker added 2026-09-04: once the cloud client reports its
    daily quota is exhausted (CloudQuotaExhaustedError), no further
    escalation attempts are made for the rest of this run - not even one
    HTTP call - rather than re-discovering the same exhaustion on every
    subsequent job. Resets naturally on the next run, since quota is a
    daily, external condition, not a per-job one.
    """

    def __init__(
        self,
        local_client: LLMClient,
        cloud_client: LLMClient,
        review_threshold: int,
        approval_threshold: int,
    ) -> None:
        self._local = local_client
        self._cloud = cloud_client
        self._review_threshold = review_threshold
        self._approval_threshold = approval_threshold
        self._cloud_quota_exhausted = False

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        local_result = self._local.evaluate_match(resume, job_title, job_description)

        if local_result.score < self._review_threshold:
            return local_result

        if self._cloud_quota_exhausted:
            log.info(
                "Local score %d for %r would normally escalate, but "
                "cloud quota is already known exhausted this run - "
                "skipping the call rather than re-confirming it.",
                local_result.score, job_title,
            )
            raise CloudQuotaExhaustedError(
                f"Cloud quota already exhausted this run - {job_title!r} "
                "needs cloud verification but none was attempted."
            )

        log.info(
            "Local score %d for %r is >= review_threshold (%d) - "
            "escalating to cloud (local scoring is no longer trusted at "
            "or above this bound, following two confirmed high-score "
            "failure modes)",
            local_result.score, job_title, self._review_threshold,
        )
        try:
            return self._cloud.evaluate_match(resume, job_title, job_description)
        except CloudQuotaExhaustedError:
            self._cloud_quota_exhausted = True
            log.error(
                "Cloud quota exhausted - no further escalation attempts "
                "will be made for the rest of this run."
            )
            raise

    def draft_answer(
        self,
        question: str,
        story_title: str,
        story_text: str,
        job_title: str,
        job_description: str,
    ) -> str:
        return self._local.draft_answer(
            question, story_title, story_text, job_title, job_description
        )

    def select_dropdown_option(
        self, question: str, options: list[str], candidate_context: str
    ) -> DropdownSelection:
        return self._local.select_dropdown_option(question, options, candidate_context)
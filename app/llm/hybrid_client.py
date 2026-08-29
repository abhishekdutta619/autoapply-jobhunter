from __future__ import annotations

import logging

from app.llm.base import DropdownSelection, EvaluationResult, LLMClient

log = logging.getLogger("llm.hybrid")


class HybridEvaluator:
    """Bulk jobs -> local model -> clear reject/clear match (done) or
    ambiguous (escalate to cloud for a second opinion).

    Exists because of a very concrete constraint found this session: a
    free-tier cloud model's daily quota (as low as 20 requests/day for a
    new preview model) makes evaluating a large queue entirely on cloud
    impractical, but a local model alone has its own real issues (thermal
    throttling, thinking-mode overhead depending on model). This spends
    the scarce cloud budget only on jobs the local model itself is unsure
    about - reusing your existing review_threshold/approval_threshold
    bounds as the definition of "unsure", rather than introducing a
    separate threshold concept.

    evaluate_match() is the only method this actually makes hybrid.
    draft_answer() and select_dropdown_option() delegate to the local
    client only - there's no natural "ambiguous" signal for a drafted
    answer or a dropdown pick the way there is for a numeric score, and
    those are Phase 3 (Executor) concerns that haven't been run against
    real applications yet regardless.
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

    def evaluate_match(
        self, resume: str, job_title: str, job_description: str
    ) -> EvaluationResult:
        local_result = self._local.evaluate_match(resume, job_title, job_description)

        if self._review_threshold <= local_result.score <= self._approval_threshold:
            log.info(
                "Local score %d is ambiguous (%d-%d band) for %r - escalating to cloud",
                local_result.score, self._review_threshold, self._approval_threshold, job_title,
            )
            # Let this raise on failure (e.g. daily quota exhausted) rather
            # than silently falling back to the uncertain local result -
            # evaluate_job()'s caller already catches and retries next run,
            # same as any other transient evaluation failure.
            cloud_result = self._cloud.evaluate_match(resume, job_title, job_description)
            return cloud_result

        # Clear reject or clear match - trust the local model, save the
        # cloud call for a job that actually needs it.
        return local_result

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
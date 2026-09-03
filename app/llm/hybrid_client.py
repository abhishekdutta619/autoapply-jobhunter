from __future__ import annotations

import logging

from app.llm.base import DropdownSelection, EvaluationResult, LLMClient

log = logging.getLogger("llm.hybrid")


class HybridEvaluator:
    """Bulk jobs -> local model -> clear reject (done) or anything else
    (escalate to cloud for a second opinion).

    Exists because of a very concrete constraint found this session: a
    free-tier cloud model's daily quota (as low as 20 requests/day for a
    new preview model) makes evaluating a large queue entirely on cloud
    impractical, but a local model alone has its own real issues (thermal
    throttling, thinking-mode overhead depending on model).

    Originally only escalated scores inside [review_threshold,
    approval_threshold] as "ambiguous," trusting local scoring fully
    above approval_threshold. That trust turned out to be misplaced: two
    separate real spot-checks (2026-09-03) found qwen3:4b producing
    confidently wrong high scores via two DIFFERENT failure modes - job
    id=160 leaked raw chain-of-thought identifying a disqualifying gap
    and scored 100 anyway; job id=268 fabricated a plausible-sounding but
    unsupported equivalence (reframing unrelated experience as meeting
    the role's actual requirements) with no admitted gap at all, also
    scored 100. An intermediate fix tried catching the first failure mode
    via a reasoning-text phrase list - it missed job 268 entirely, since
    confabulation doesn't contain any of the trigger phrases a stated-
    then-ignored gap would. Given two structurally distinct ways to be
    wrong in the same score range, and no evidence local scoring below
    review_threshold has ever been wrong, the local model is no longer
    trusted for APPROVE at all - only for TRASH. Every other score gets
    a cloud second opinion. This trades cloud-call volume (which was
    previously bounded to the narrow ambiguous band) for meaningfully
    higher confidence in what actually reaches APPROVED_FOR_APPLY -
    worth it given what reaches that status can eventually feed Phase 3
    (Executor) once that's in real use.

    evaluate_match() is the only method this actually makes hybrid.
    draft_answer() and select_dropdown_option() delegate to the local
    client only - see prior version of this docstring for why.
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

        if local_result.score < self._review_threshold:
            # Clear reject - no confirmed failure case at this end yet,
            # trust the local model and save the cloud call.
            return local_result

        log.info(
            "Local score %d for %r is >= review_threshold (%d) - "
            "escalating to cloud (local scoring is no longer trusted at "
            "or above this bound, following two confirmed high-score "
            "failure modes)",
            local_result.score, job_title, self._review_threshold,
        )
        cloud_result = self._cloud.evaluate_match(resume, job_title, job_description)
        return cloud_result

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
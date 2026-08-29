from __future__ import annotations

from app.llm.base import DropdownSelection, EvaluationResult
from app.llm.hybrid_client import HybridEvaluator


class StubClient:
    """Records every call it receives - lets tests assert whether the
    cloud client was ever actually invoked, not just what it returned."""

    def __init__(self, score: int = 50, reasoning: str = "stub reasoning"):
        self.score = score
        self.reasoning = reasoning
        self.evaluate_calls: list[tuple] = []

    def evaluate_match(self, resume, job_title, job_description) -> EvaluationResult:
        self.evaluate_calls.append((resume, job_title, job_description))
        return EvaluationResult(score=self.score, reasoning=self.reasoning)

    def draft_answer(self, question, story_title, story_text, job_title, job_description) -> str:
        return f"answer for {question}"

    def select_dropdown_option(self, question, options, candidate_context) -> DropdownSelection:
        return DropdownSelection(selected_option=options[0], confidence="high")


def _hybrid(local_score: int, cloud_score: int = 90, review_threshold=60, approval_threshold=85):
    local = StubClient(score=local_score, reasoning="local verdict")
    cloud = StubClient(score=cloud_score, reasoning="cloud verdict")
    hybrid = HybridEvaluator(
        local_client=local, cloud_client=cloud,
        review_threshold=review_threshold, approval_threshold=approval_threshold,
    )
    return hybrid, local, cloud


def test_clear_reject_never_touches_cloud():
    hybrid, local, cloud = _hybrid(local_score=20)  # well below review_threshold=60
    result = hybrid.evaluate_match("resume", "title", "description")

    assert result.score == 20
    assert result.reasoning == "local verdict"
    assert len(local.evaluate_calls) == 1
    assert len(cloud.evaluate_calls) == 0  # the whole point - never spend the cloud budget here


def test_clear_match_never_touches_cloud():
    hybrid, local, cloud = _hybrid(local_score=95)  # well above approval_threshold=85
    result = hybrid.evaluate_match("resume", "title", "description")

    assert result.score == 95
    assert result.reasoning == "local verdict"
    assert len(cloud.evaluate_calls) == 0


def test_ambiguous_score_escalates_to_cloud_and_cloud_wins():
    hybrid, local, cloud = _hybrid(local_score=70, cloud_score=88)  # 70 is in [60, 85]
    result = hybrid.evaluate_match("resume", "title", "description")

    assert len(local.evaluate_calls) == 1
    assert len(cloud.evaluate_calls) == 1
    # Cloud's verdict is what gets returned for ambiguous cases, not local's.
    assert result.score == 88
    assert result.reasoning == "cloud verdict"


def test_lower_boundary_is_inclusive():
    # score == review_threshold exactly should still count as ambiguous.
    hybrid, local, cloud = _hybrid(local_score=60)
    hybrid.evaluate_match("resume", "title", "description")
    assert len(cloud.evaluate_calls) == 1


def test_upper_boundary_is_inclusive():
    # score == approval_threshold exactly should still count as ambiguous.
    hybrid, local, cloud = _hybrid(local_score=85)
    hybrid.evaluate_match("resume", "title", "description")
    assert len(cloud.evaluate_calls) == 1


def test_just_below_lower_boundary_does_not_escalate():
    hybrid, local, cloud = _hybrid(local_score=59)
    hybrid.evaluate_match("resume", "title", "description")
    assert len(cloud.evaluate_calls) == 0


def test_just_above_upper_boundary_does_not_escalate():
    hybrid, local, cloud = _hybrid(local_score=86)
    hybrid.evaluate_match("resume", "title", "description")
    assert len(cloud.evaluate_calls) == 0


def test_cloud_failure_on_ambiguous_job_propagates_instead_of_silently_falling_back():
    """A failed cloud call (e.g. daily quota exhausted) should raise, not
    silently return the uncertain local result as if nothing went wrong -
    evaluate_job()'s caller already handles retrying failed jobs next run."""
    class FailingCloud:
        def evaluate_match(self, *a, **kw):
            raise RuntimeError("quota exhausted")

    local = StubClient(score=70)
    hybrid = HybridEvaluator(
        local_client=local, cloud_client=FailingCloud(),
        review_threshold=60, approval_threshold=85,
    )

    try:
        hybrid.evaluate_match("resume", "title", "description")
        assert False, "expected the cloud failure to propagate"
    except RuntimeError as exc:
        assert "quota exhausted" in str(exc)


def test_draft_answer_delegates_to_local_only():
    hybrid, local, cloud = _hybrid(local_score=70)
    answer = hybrid.draft_answer("Tell me about a win", "Story", "text", "title", "description")
    assert answer == "answer for Tell me about a win"


def test_select_dropdown_option_delegates_to_local_only():
    hybrid, local, cloud = _hybrid(local_score=70)
    result = hybrid.select_dropdown_option("Years?", ["3-5", "5+"], "context")
    assert result.selected_option == "3-5"
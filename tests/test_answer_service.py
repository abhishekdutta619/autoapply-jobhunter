from __future__ import annotations

from app.rag.answer_service import AnswerService
from app.rag.retriever import StoryRetriever
from app.rag.story_bank import Story


class StubLLMClient:
    """Records what it was asked and returns a fixed answer - no network."""

    def __init__(self):
        self.calls = []

    def evaluate_match(self, resume, job_title, job_description):
        raise NotImplementedError("not used by AnswerService")

    def draft_answer(self, question, story_title, story_text, job_title, job_description):
        self.calls.append(
            dict(
                question=question,
                story_title=story_title,
                story_text=story_text,
                job_title=job_title,
                job_description=job_description,
            )
        )
        return f"Drafted answer grounded in {story_title!r}."


def test_answer_service_retrieves_then_generates():
    stories = [
        Story(title="Incident Response", tags=["debugging"], text="Fixed an outage."),
        Story(title="Mentorship", tags=["mentoring"], text="Mentored a junior engineer."),
    ]
    retriever = StoryRetriever(stories)
    stub_llm = StubLLMClient()
    service = AnswerService(retriever, stub_llm)

    answer, story = service.draft_answer(
        question="Tell us about a time you mentored someone.",
        job_title="Senior Engineer",
        job_description="...",
    )

    assert story.title == "Mentorship"
    assert "Mentorship" in answer
    assert stub_llm.calls[0]["story_title"] == "Mentorship"
    assert stub_llm.calls[0]["job_title"] == "Senior Engineer"

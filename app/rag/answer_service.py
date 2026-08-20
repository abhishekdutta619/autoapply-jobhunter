from __future__ import annotations

from app.llm.base import LLMClient
from app.rag.retriever import StoryRetriever
from app.rag.story_bank import Story


class AnswerService:
    def __init__(self, retriever: StoryRetriever, llm_client: LLMClient):
        self._retriever = retriever
        self._llm_client = llm_client

    def draft_answer(
        self, question: str, job_title: str, job_description: str
    ) -> tuple[str, Story]:
        """Returns (drafted_answer, story_used) - the story is returned too
        so callers can tell the human which story grounded the draft.
        """
        story = self._retriever.best_match(question)
        answer = self._llm_client.draft_answer(
            question=question,
            story_title=story.title,
            story_text=story.text,
            job_title=job_title,
            job_description=job_description,
        )
        return answer, story

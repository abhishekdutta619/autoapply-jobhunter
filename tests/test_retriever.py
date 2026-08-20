from __future__ import annotations

import pytest

from app.rag.retriever import StoryRetriever
from app.rag.story_bank import Story


@pytest.fixture()
def retriever() -> StoryRetriever:
    stories = [
        Story(
            title="Migrating payments to microservices",
            tags=["leadership", "distributed systems", "migration"],
            text=(
                "I led a migration from a payments monolith to microservices "
                "using Kafka and gRPC, coordinating four engineers over six "
                "months with zero downtime."
            ),
        ),
        Story(
            title="Debugging a production outage",
            tags=["problem solving", "incident response", "debugging"],
            text=(
                "During a Black Friday traffic spike our checkout service "
                "started failing. I traced it to connection pool exhaustion "
                "and shipped a hotfix within 25 minutes."
            ),
        ),
        Story(
            title="Mentoring a junior engineer",
            tags=["mentorship", "leadership", "growth"],
            text=(
                "I mentored a junior engineer through their first on-call "
                "rotation, pairing weekly and reviewing their incident "
                "postmortems until they were running rotations solo."
            ),
        ),
    ]
    return StoryRetriever(stories)


def test_retrieves_the_most_relevant_story_for_incident_question(retriever):
    question = "Tell us about a time you handled a production incident."
    match = retriever.best_match(question)
    assert match.title == "Debugging a production outage"


def test_retrieves_the_most_relevant_story_for_architecture_question(retriever):
    question = "Describe your experience with distributed systems and migrations."
    match = retriever.best_match(question)
    assert match.title == "Migrating payments to microservices"


def test_retrieves_the_most_relevant_story_for_mentorship_question(retriever):
    question = "Tell us about a time you mentored someone on your team."
    match = retriever.best_match(question)
    assert match.title == "Mentoring a junior engineer"


def test_empty_story_list_raises():
    with pytest.raises(ValueError, match="empty"):
        StoryRetriever([])

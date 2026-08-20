from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.config import settings


class Story(BaseModel):
    """One real project/experience the candidate can draw on when an
    application asks an open-ended question ('Describe a time you...').
    """

    title: str
    tags: list[str] = []
    text: str


def load_stories(path: str | None = None) -> list[Story]:
    story_path = Path(path or settings.story_bank_path)
    if not story_path.exists():
        raise FileNotFoundError(
            f"No story bank found at {story_path}. Copy story_bank.json.example "
            "to that path and add 2-5 real stories - the Executor will skip "
            "cover letter / open-question fields entirely until it exists."
        )
    data = json.loads(story_path.read_text())
    stories = [Story(**item) for item in data]
    if not stories:
        raise ValueError(f"{story_path} exists but contains no stories.")
    return stories

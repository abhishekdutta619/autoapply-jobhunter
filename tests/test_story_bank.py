from __future__ import annotations

import json

import pytest

from app.rag.story_bank import load_stories


def test_missing_story_bank_raises_clear_error(tmp_path):
    missing_path = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError, match="story_bank.json.example"):
        load_stories(str(missing_path))


def test_empty_story_bank_raises_clear_error(tmp_path):
    path = tmp_path / "story_bank.json"
    path.write_text("[]")
    with pytest.raises(ValueError, match="no stories"):
        load_stories(str(path))


def test_valid_story_bank_loads_successfully(tmp_path):
    path = tmp_path / "story_bank.json"
    path.write_text(
        json.dumps(
            [
                {"title": "Story One", "tags": ["leadership"], "text": "Did a thing."},
                {"title": "Story Two", "text": "Did another thing."},
            ]
        )
    )
    stories = load_stories(str(path))
    assert len(stories) == 2
    assert stories[0].title == "Story One"
    assert stories[1].tags == []  # tags default to empty list

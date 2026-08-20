from __future__ import annotations

import json

import pytest

from app.executor.candidate import load_candidate_profile


def test_missing_profile_file_raises_clear_error(tmp_path):
    missing_path = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError, match="candidate_profile.json.example"):
        load_candidate_profile(str(missing_path))


def test_missing_resume_file_raises_clear_error(tmp_path):
    profile_path = tmp_path / "candidate_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "resume_file_path": str(tmp_path / "does_not_exist.pdf"),
            }
        )
    )
    with pytest.raises(FileNotFoundError, match="resume_file_path"):
        load_candidate_profile(str(profile_path))


def test_valid_profile_loads_successfully(tmp_path):
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_text("dummy pdf content")

    profile_path = tmp_path / "candidate_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "resume_file_path": str(resume_file),
            }
        )
    )

    profile = load_candidate_profile(str(profile_path))
    assert profile.first_name == "Jane"
    assert profile.github_url is None

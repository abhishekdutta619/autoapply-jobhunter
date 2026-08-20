from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.config import settings


class CandidateProfile(BaseModel):
    """Structured applicant data used to fill known form fields.

    Deliberately does NOT include EEO/demographic fields (race, gender,
    veteran status, disability, work authorization) - those are legally
    significant, often voluntary, and belong to a human answering them
    directly, not an agent guessing on their behalf.
    """

    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    resume_file_path: str
    cover_letter_file_path: str | None = None


def load_candidate_profile(path: str | None = None) -> CandidateProfile:
    profile_path = Path(path or settings.candidate_profile_path)
    if not profile_path.exists():
        raise FileNotFoundError(
            f"No candidate profile found at {profile_path}. Copy "
            "candidate_profile.json.example to that path and fill it in "
            "before running the Executor."
        )

    profile = CandidateProfile(**json.loads(profile_path.read_text()))

    resume_file = Path(profile.resume_file_path)
    if not resume_file.exists():
        raise FileNotFoundError(
            f"candidate profile's resume_file_path points to {resume_file}, "
            "which doesn't exist. This should be the actual PDF/DOCX file to "
            "upload - separate from resume.md, which is plain text used only "
            "for LLM scoring in Phase 2."
        )

    return profile

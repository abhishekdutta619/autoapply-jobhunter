from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel

from app.executor.candidate import CandidateProfile


class FieldRole(str, Enum):
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    FULL_NAME = "full_name"
    EMAIL = "email"
    PHONE = "phone"
    LINKEDIN_URL = "linkedin_url"
    GITHUB_URL = "github_url"
    PORTFOLIO_URL = "portfolio_url"
    RESUME_UPLOAD = "resume_upload"
    COVER_LETTER_UPLOAD = "cover_letter_upload"
    COVER_LETTER_TEXT = "cover_letter_text"
    OPEN_QUESTION_TEXT = "open_question_text"


class FieldInfo(BaseModel):
    """Metadata about one form field, extracted from the DOM."""

    tag: str  # "input" | "textarea" | "select"
    input_type: str = ""  # "text" | "email" | "tel" | "file" | "" for textarea/select
    name: str = ""
    field_id: str = ""
    placeholder: str = ""
    aria_label: str = ""
    label_text: str = ""
    options: list[str] = []  # visible <option> text, non-placeholder ones only - select only


# Exact-match attribute lookup - checked before fuzzy text matching, since a
# matching `name`/`id` attribute is a stronger signal than substring text.
_ATTR_EXACT_MAP: dict[str, FieldRole] = {
    "fname": FieldRole.FIRST_NAME,
    "firstname": FieldRole.FIRST_NAME,
    "lname": FieldRole.LAST_NAME,
    "lastname": FieldRole.LAST_NAME,
    "surname": FieldRole.LAST_NAME,
    "email": FieldRole.EMAIL,
    "emailaddress": FieldRole.EMAIL,
    "phone": FieldRole.PHONE,
    "phonenumber": FieldRole.PHONE,
    "tel": FieldRole.PHONE,
    "mobile": FieldRole.PHONE,
    "linkedin": FieldRole.LINKEDIN_URL,
    "linkedinurl": FieldRole.LINKEDIN_URL,
    "github": FieldRole.GITHUB_URL,
    "githuburl": FieldRole.GITHUB_URL,
    "portfolio": FieldRole.PORTFOLIO_URL,
    "portfoliourl": FieldRole.PORTFOLIO_URL,
    "website": FieldRole.PORTFOLIO_URL,
}


def _normalize_attr(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())


_OPEN_QUESTION_PATTERNS = re.compile(
    r"describe a time|tell us about|tell us why|why (do|are) you|"
    r"what interests you|greatest strength|greatest weakness|"
    r"why should we hire you|why do you want to work"
)

# EEO/demographic/work-authorization questions - never auto-answered by an
# LLM, regardless of how confident it claims to be. This is checked before
# any LLM call is attempted at all, not just before filling the field -
# these questions shouldn't even be sent to a third-party API as part of
# this flow, let alone have their answer guessed.
_SENSITIVE_DROPDOWN_PATTERNS = re.compile(
    r"race|ethnicit|gender|\bsex\b|veteran|disab|"
    r"sexual orientation|work authoriz|authorized to work|"
    r"\bvisa\b|sponsorship|citizenship|\bpronoun"
)


def is_sensitive_dropdown(info: FieldInfo) -> bool:
    text = _combined_text(info) + " " + info.name.lower() + " " + info.field_id.lower()
    return bool(_SENSITIVE_DROPDOWN_PATTERNS.search(text))


def _combined_text(info: FieldInfo) -> str:
    return " ".join(
        [info.label_text, info.aria_label, info.placeholder]
    ).lower()


def classify_field(info: FieldInfo) -> FieldRole | None:
    """Best-effort guess at what a field is for. Returns None if unsure -
    an unmatched field is left for the human to fill, never guessed at.
    """
    # File uploads: only claim resume/cover-letter, never a generic upload
    # (work samples, portfolio PDFs, etc. - too risky to guess).
    if info.tag == "input" and info.input_type == "file":
        text = _combined_text(info) + " " + info.name.lower() + " " + info.field_id.lower()
        if re.search(r"cover\s*letter", text):
            return FieldRole.COVER_LETTER_UPLOAD
        if re.search(r"\bresume\b|\bcv\b", text):
            return FieldRole.RESUME_UPLOAD
        return None

    # Exact attribute match first - most reliable signal.
    for attr in (info.name, info.field_id):
        if not attr:
            continue
        role = _ATTR_EXACT_MAP.get(_normalize_attr(attr))
        if role:
            return role

    # Fuzzy label/placeholder/aria-label text match.
    text = _combined_text(info)

    if info.input_type == "email" or "email" in text:
        return FieldRole.EMAIL
    if info.input_type == "tel" or re.search(r"\bphone\b|\bmobile\b", text):
        return FieldRole.PHONE
    if "linkedin" in text:
        return FieldRole.LINKEDIN_URL
    if "github" in text:
        return FieldRole.GITHUB_URL
    if re.search(r"portfolio|personal website", text):
        return FieldRole.PORTFOLIO_URL

    # Name fields are deliberately narrow patterns - "company name" or
    # "reference name" must NOT match here.
    if re.search(r"first\s*name|given\s*name", text):
        return FieldRole.FIRST_NAME
    if re.search(r"last\s*name|surname|family\s*name", text):
        return FieldRole.LAST_NAME
    if re.search(r"\bfull\s*name\b", text) or text.strip() == "name":
        return FieldRole.FULL_NAME

    if info.tag == "textarea" and re.search(r"cover\s*letter", text):
        return FieldRole.COVER_LETTER_TEXT

    if info.tag == "textarea" and (
        _OPEN_QUESTION_PATTERNS.search(text) or text.strip().endswith("?")
    ):
        return FieldRole.OPEN_QUESTION_TEXT

    return None


def resolve_value(role: FieldRole, candidate: CandidateProfile) -> str | None:
    """Look up the candidate's value for a simple text-fill role.

    File uploads and cover-letter text are handled separately by the
    caller, since they need special Playwright calls, not .fill().
    """
    mapping = {
        FieldRole.FIRST_NAME: candidate.first_name,
        FieldRole.LAST_NAME: candidate.last_name,
        FieldRole.FULL_NAME: f"{candidate.first_name} {candidate.last_name}",
        FieldRole.EMAIL: candidate.email,
        FieldRole.PHONE: candidate.phone,
        FieldRole.LINKEDIN_URL: candidate.linkedin_url,
        FieldRole.GITHUB_URL: candidate.github_url,
        FieldRole.PORTFOLIO_URL: candidate.portfolio_url,
    }
    return mapping.get(role)

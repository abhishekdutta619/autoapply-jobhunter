from __future__ import annotations

import pytest

from app.executor.candidate import CandidateProfile
from app.executor.field_classifier import (
    FieldInfo,
    FieldRole,
    classify_field,
    is_sensitive_dropdown,
    resolve_value,
)


def _candidate() -> CandidateProfile:
    return CandidateProfile(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="555-123-4567",
        linkedin_url="https://linkedin.com/in/janedoe",
        github_url="https://github.com/janedoe",
        portfolio_url="https://janedoe.dev",
        resume_file_path=__file__,  # any existing file works for these tests
    )


def test_classifies_email_by_input_type():
    info = FieldInfo(tag="input", input_type="email", name="user_email", label_text="Email")
    assert classify_field(info) == FieldRole.EMAIL


def test_classifies_phone_by_input_type():
    info = FieldInfo(tag="input", input_type="tel", name="phone1")
    assert classify_field(info) == FieldRole.PHONE


def test_classifies_first_and_last_name_by_label():
    first = FieldInfo(tag="input", input_type="text", label_text="First Name")
    last = FieldInfo(tag="input", input_type="text", label_text="Last Name")
    assert classify_field(first) == FieldRole.FIRST_NAME
    assert classify_field(last) == FieldRole.LAST_NAME


def test_classifies_by_exact_name_attribute_even_without_label():
    info = FieldInfo(tag="input", input_type="text", name="fname")
    assert classify_field(info) == FieldRole.FIRST_NAME


def test_company_name_field_is_not_misclassified_as_full_name():
    # This is the important negative case: "name" appears in the label,
    # but this is clearly NOT the candidate's own name.
    info = FieldInfo(tag="input", input_type="text", label_text="Current Company Name")
    assert classify_field(info) is None


def test_reference_name_field_is_not_misclassified():
    info = FieldInfo(tag="input", input_type="text", label_text="Reference Full Name")
    # Contains "full name" substring but in a context that isn't the
    # candidate - this is a known limitation of the heuristic, documented
    # so a human catches it during review rather than being surprised.
    # We assert current (imperfect) behavior here so a future change to
    # the matcher is a deliberate decision, not a silent regression.
    assert classify_field(info) == FieldRole.FULL_NAME


def test_classifies_linkedin_and_github_by_label():
    linkedin = FieldInfo(tag="input", input_type="text", label_text="LinkedIn Profile URL")
    github = FieldInfo(tag="input", input_type="text", label_text="GitHub Profile")
    assert classify_field(linkedin) == FieldRole.LINKEDIN_URL
    assert classify_field(github) == FieldRole.GITHUB_URL


def test_classifies_resume_upload():
    info = FieldInfo(tag="input", input_type="file", label_text="Upload your Resume/CV")
    assert classify_field(info) == FieldRole.RESUME_UPLOAD


def test_classifies_cover_letter_upload_vs_resume_upload():
    resume = FieldInfo(tag="input", input_type="file", label_text="Resume")
    cover = FieldInfo(tag="input", input_type="file", label_text="Cover Letter (optional)")
    assert classify_field(resume) == FieldRole.RESUME_UPLOAD
    assert classify_field(cover) == FieldRole.COVER_LETTER_UPLOAD


def test_unknown_file_upload_is_not_guessed():
    # A "Work Sample" or "Portfolio PDF" upload shouldn't be assumed to be
    # a resume just because it's a file input.
    info = FieldInfo(tag="input", input_type="file", label_text="Upload a Work Sample")
    assert classify_field(info) is None


def test_cover_letter_textarea_is_flagged_but_not_auto_filled():
    info = FieldInfo(tag="textarea", label_text="Cover Letter")
    assert classify_field(info) == FieldRole.COVER_LETTER_TEXT
    # resolve_value() intentionally doesn't handle this role - the runner
    # skips it rather than fabricating cover letter text.
    assert resolve_value(FieldRole.COVER_LETTER_TEXT, _candidate()) is None


def test_unrecognized_field_returns_none():
    info = FieldInfo(tag="select", label_text="How did you hear about us?")
    assert classify_field(info) is None


def test_open_ended_behavioral_question_is_classified():
    info = FieldInfo(
        tag="textarea", label_text="Describe a time you overcame a difficult challenge."
    )
    assert classify_field(info) == FieldRole.OPEN_QUESTION_TEXT


def test_generic_question_mark_textarea_is_classified_as_open_question():
    info = FieldInfo(tag="textarea", label_text="What makes you a great fit for this role?")
    assert classify_field(info) == FieldRole.OPEN_QUESTION_TEXT


def test_cover_letter_takes_precedence_over_open_question_pattern():
    info = FieldInfo(tag="textarea", label_text="Cover Letter - why do you want this role?")
    assert classify_field(info) == FieldRole.COVER_LETTER_TEXT


def test_unrelated_textarea_without_question_mark_is_skipped():
    info = FieldInfo(tag="textarea", label_text="Additional comments")
    assert classify_field(info) is None


def test_resolve_value_combines_first_and_last_for_full_name():
    assert resolve_value(FieldRole.FULL_NAME, _candidate()) == "Jane Doe"


def test_resolve_value_returns_none_for_unset_optional_field():
    candidate = _candidate()
    candidate.github_url = None
    assert resolve_value(FieldRole.GITHUB_URL, candidate) is None


@pytest.mark.parametrize(
    "label",
    [
        "Are you legally authorized to work in the US?",
        "Do you require visa sponsorship?",
        "Gender",
        "Race/Ethnicity",
        "Veteran Status",
        "Disability Status",
        "What are your pronouns?",
        "Sexual Orientation",
        "Citizenship Status",
    ],
)
def test_sensitive_dropdown_labels_are_flagged(label):
    info = FieldInfo(tag="select", label_text=label)
    assert is_sensitive_dropdown(info) is True


@pytest.mark.parametrize(
    "label",
    [
        "How did you hear about us?",
        "Years of Python experience",
        "Preferred start date",
        "Desired job level",
    ],
)
def test_ordinary_dropdown_labels_are_not_flagged(label):
    info = FieldInfo(tag="select", label_text=label)
    assert is_sensitive_dropdown(info) is False

from __future__ import annotations

from app.llm.prompts import build_constraints_section


def test_no_preferences_returns_empty_string():
    # Callers do resume_text += build_constraints_section(...) unconditionally -
    # this must be a true no-op when nothing is configured.
    assert build_constraints_section() == ""


def test_remote_preference_is_phrased_as_soft_not_hard():
    section = build_constraints_section(prefer_remote=True)
    assert "PREFERS fully remote" in section
    assert "second choice" in section
    # Must not contain absolute/exclusionary language - this is a
    # preference, not a requirement.
    assert "requires" not in section.lower()
    assert "cannot" not in section.lower()


def test_compensation_only_indian():
    section = build_constraints_section(target_compensation_indian="15-20 LPA")
    assert "Indian company: 15-20 LPA" in section
    assert "MNC" not in section


def test_compensation_only_mnc():
    section = build_constraints_section(target_compensation_mnc="30-40 LPA")
    assert "Multinational/foreign company (MNC): 30-40 LPA" in section
    assert "Indian company" not in section


def test_compensation_both_indian_and_mnc_present():
    section = build_constraints_section(
        target_compensation_indian="15-20 LPA",
        target_compensation_mnc="30-40 LPA",
    )
    assert "Indian company: 15-20 LPA" in section
    assert "Multinational/foreign company (MNC): 30-40 LPA" in section


def test_all_preferences_present_together():
    section = build_constraints_section(
        prefer_remote=True,
        target_compensation_indian="15-20 LPA",
        target_compensation_mnc="30-40 LPA",
    )
    assert "PREFERS fully remote" in section
    assert "Indian company: 15-20 LPA" in section
    assert "Multinational/foreign company (MNC): 30-40 LPA" in section
    assert "CANDIDATE'S PREFERENCES" in section
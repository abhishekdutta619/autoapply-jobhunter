from __future__ import annotations

from app.executor.dropdown_mapper import DropdownMapper
from app.llm.base import DropdownSelection


class StubLLMClient:
    def __init__(self, selection: DropdownSelection):
        self._selection = selection
        self.calls = []

    def evaluate_match(self, resume, job_title, job_description):
        raise NotImplementedError

    def draft_answer(self, question, story_title, story_text, job_title, job_description):
        raise NotImplementedError

    def select_dropdown_option(self, question, options, candidate_context):
        self.calls.append((question, options, candidate_context))
        return self._selection


def test_high_confidence_valid_option_is_returned():
    stub = StubLLMClient(DropdownSelection(selected_option="5+ years", confidence="high"))
    mapper = DropdownMapper(stub, resume_text="resume")

    result = mapper.map_option("Years of experience?", ["0-1 years", "2-4 years", "5+ years"])

    assert result == "5+ years"


def test_none_selection_returns_none():
    stub = StubLLMClient(DropdownSelection(selected_option="NONE", confidence="high"))
    mapper = DropdownMapper(stub, resume_text="resume")

    result = mapper.map_option("Favorite color?", ["Red", "Blue"])

    assert result is None


def test_low_confidence_is_not_auto_filled_even_if_option_is_valid():
    stub = StubLLMClient(DropdownSelection(selected_option="Red", confidence="low"))
    mapper = DropdownMapper(stub, resume_text="resume")

    result = mapper.map_option("Favorite color?", ["Red", "Blue"])

    assert result is None


def test_medium_confidence_is_not_auto_filled():
    stub = StubLLMClient(DropdownSelection(selected_option="Red", confidence="medium"))
    mapper = DropdownMapper(stub, resume_text="resume")

    assert mapper.map_option("Favorite color?", ["Red", "Blue"]) is None


def test_option_not_in_provided_list_is_rejected_defensively():
    # Shouldn't happen given the schema's enum constraint, but the mapper
    # must never trust a value blindly.
    stub = StubLLMClient(DropdownSelection(selected_option="Purple", confidence="high"))
    mapper = DropdownMapper(stub, resume_text="resume")

    assert mapper.map_option("Favorite color?", ["Red", "Blue"]) is None


def test_empty_options_returns_none_without_calling_llm():
    stub = StubLLMClient(DropdownSelection(selected_option="NONE", confidence="high"))
    mapper = DropdownMapper(stub, resume_text="resume")

    result = mapper.map_option("Favorite color?", [])

    assert result is None
    assert stub.calls == []


def test_resume_text_is_passed_as_candidate_context():
    stub = StubLLMClient(DropdownSelection(selected_option="NONE", confidence="high"))
    mapper = DropdownMapper(stub, resume_text="5 years Python experience")

    mapper.map_option("Years of experience?", ["1-2", "3-5"])

    assert stub.calls[0][2] == "5 years Python experience"

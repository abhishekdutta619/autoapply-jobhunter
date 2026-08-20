from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.llm.anthropic_client import AnthropicEvaluator
from app.llm.openai_client import OpenAIEvaluator


def test_openai_client_parses_structured_response():
    fake_completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps({"score": 92, "reasoning": "Strong skills match."})
                )
            )
        ]
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion

    with patch("app.llm.openai_client.OpenAI", return_value=fake_client):
        evaluator = OpenAIEvaluator(api_key="test-key")
        result = evaluator.evaluate_match("resume text", "Backend Engineer", "job description")

    assert result.score == 92
    assert result.reasoning == "Strong skills match."
    # Confirm the model actually requested structured output, not free text.
    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs["response_format"]["type"] == "json_schema"


def test_openai_client_requires_api_key():
    try:
        OpenAIEvaluator(api_key="")
        assert False, "expected ValueError for missing API key"
    except ValueError:
        pass


def test_anthropic_client_parses_tool_use_response():
    fake_tool_block = SimpleNamespace(
        type="tool_use",
        input={"score": 78, "reasoning": "Decent but missing key requirement."},
    )
    fake_text_block = SimpleNamespace(type="text", text="thinking out loud")
    fake_response = SimpleNamespace(content=[fake_text_block, fake_tool_block])

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("app.llm.anthropic_client.Anthropic", return_value=fake_client):
        evaluator = AnthropicEvaluator(api_key="test-key")
        result = evaluator.evaluate_match("resume text", "Backend Engineer", "job description")

    assert result.score == 78
    assert result.reasoning == "Decent but missing key requirement."
    # Confirm tool use was forced, not left optional.
    _, kwargs = fake_client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "submit_evaluation"}


def test_anthropic_client_requires_api_key():
    try:
        AnthropicEvaluator(api_key="")
        assert False, "expected ValueError for missing API key"
    except ValueError:
        pass


def test_openai_client_drafts_answer_from_text_response():
    fake_completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="  I led a migration effort...  ")
            )
        ]
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion

    with patch("app.llm.openai_client.OpenAI", return_value=fake_client):
        evaluator = OpenAIEvaluator(api_key="test-key")
        answer = evaluator.draft_answer(
            question="Describe a time you led a project.",
            story_title="Migration",
            story_text="Led a migration...",
            job_title="Backend Engineer",
            job_description="...",
        )

    assert answer == "I led a migration effort..."  # whitespace stripped
    # Structured output should NOT be requested here - this is free text.
    _, kwargs = fake_client.chat.completions.create.call_args
    assert "response_format" not in kwargs


def test_anthropic_client_drafts_answer_from_text_block():
    fake_text_block = SimpleNamespace(type="text", text="  I led a migration effort...  ")
    fake_response = SimpleNamespace(content=[fake_text_block])

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("app.llm.anthropic_client.Anthropic", return_value=fake_client):
        evaluator = AnthropicEvaluator(api_key="test-key")
        answer = evaluator.draft_answer(
            question="Describe a time you led a project.",
            story_title="Migration",
            story_text="Led a migration...",
            job_title="Backend Engineer",
            job_description="...",
        )

    assert answer == "I led a migration effort..."
    # No forced tool use here - free text generation, not structured scoring.
    _, kwargs = fake_client.messages.create.call_args
    assert "tools" not in kwargs


def test_openai_client_selects_dropdown_option_from_structured_response():
    fake_completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps({"selected_option": "5+ years", "confidence": "high"})
                )
            )
        ]
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion

    with patch("app.llm.openai_client.OpenAI", return_value=fake_client):
        evaluator = OpenAIEvaluator(api_key="test-key")
        selection = evaluator.select_dropdown_option(
            question="Years of Python experience?",
            options=["0-1 years", "2-4 years", "5+ years"],
            candidate_context="5 years of Python backend experience.",
        )

    assert selection.selected_option == "5+ years"
    assert selection.confidence == "high"
    # The exact option set must be embedded in the schema's enum.
    _, kwargs = fake_client.chat.completions.create.call_args
    enum_values = kwargs["response_format"]["json_schema"]["schema"]["properties"][
        "selected_option"
    ]["enum"]
    assert enum_values == ["0-1 years", "2-4 years", "5+ years", "NONE"]


def test_anthropic_client_selects_dropdown_option_from_tool_use():
    fake_tool_block = SimpleNamespace(
        type="tool_use",
        input={"selected_option": "NONE", "confidence": "low"},
    )
    fake_response = SimpleNamespace(content=[fake_tool_block])

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("app.llm.anthropic_client.Anthropic", return_value=fake_client):
        evaluator = AnthropicEvaluator(api_key="test-key")
        selection = evaluator.select_dropdown_option(
            question="Preferred pet?",
            options=["Cats", "Dogs"],
            candidate_context="No pet preference stated in resume.",
        )

    assert selection.selected_option == "NONE"
    assert selection.confidence == "low"
    _, kwargs = fake_client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "select_dropdown_option"}

from __future__ import annotations

import json
from unittest.mock import patch

import httpx

from app.llm.ollama_client import OllamaEvaluator


def _mock_response(content: str):
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    body = {"message": {"role": "assistant", "content": content}}
    return httpx.Response(status_code=200, json=body, request=request)


def test_evaluate_match_parses_structured_response():
    fake_content = json.dumps({"score": 88, "reasoning": "Strong skills overlap."})

    with patch("httpx.post", return_value=_mock_response(fake_content)) as mock_post:
        evaluator = OllamaEvaluator(model="llama3.1:8b")
        result = evaluator.evaluate_match("resume text", "Backend Engineer", "job description")

    assert result.score == 88
    assert result.reasoning == "Strong skills overlap."

    # Confirm a schema was actually passed via Ollama's `format` field -
    # the mechanism that constrains decoding, same idea as the cloud
    # providers' structured outputs.
    _, kwargs = mock_post.call_args
    assert "format" in kwargs["json"]
    assert kwargs["json"]["format"]["properties"]["score"]["type"] == "integer"
    # Determinism for schema-constrained generation, per Ollama's own guidance.
    assert kwargs["json"]["options"]["temperature"] == 0


def test_draft_answer_does_not_request_structured_format():
    with patch("httpx.post", return_value=_mock_response("  I led a migration...  ")) as mock_post:
        evaluator = OllamaEvaluator(model="llama3.1:8b")
        answer = evaluator.draft_answer(
            question="Describe a time you led a project.",
            story_title="Migration",
            story_text="Led a migration...",
            job_title="Backend Engineer",
            job_description="...",
        )

    assert answer == "I led a migration..."
    _, kwargs = mock_post.call_args
    assert "format" not in kwargs["json"]  # free text, not schema-constrained


def test_select_dropdown_option_embeds_options_in_schema_enum():
    fake_content = json.dumps({"selected_option": "5+ years", "confidence": "high"})

    with patch("httpx.post", return_value=_mock_response(fake_content)) as mock_post:
        evaluator = OllamaEvaluator(model="llama3.1:8b")
        selection = evaluator.select_dropdown_option(
            question="Years of Python experience?",
            options=["0-1 years", "2-4 years", "5+ years"],
            candidate_context="5 years of Python backend experience.",
        )

    assert selection.selected_option == "5+ years"
    assert selection.confidence == "high"
    _, kwargs = mock_post.call_args
    enum_values = kwargs["json"]["format"]["properties"]["selected_option"]["enum"]
    assert enum_values == ["0-1 years", "2-4 years", "5+ years", "NONE"]


def test_connection_error_raises_helpful_message():
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        evaluator = OllamaEvaluator(base_url="http://localhost:11434", model="llama3.1:8b")
        try:
            evaluator.evaluate_match("resume", "title", "description")
            assert False, "expected ConnectionError"
        except ConnectionError as exc:
            assert "ollama serve" in str(exc)
            assert "llama3.1:8b" in str(exc)


def test_custom_base_url_is_used():
    with patch("httpx.post", return_value=_mock_response(json.dumps({"score": 50, "reasoning": "x"}))) as mock_post:
        evaluator = OllamaEvaluator(base_url="http://192.168.1.50:11434", model="llama3.1:8b")
        evaluator.evaluate_match("resume", "title", "description")

    called_url = mock_post.call_args[0][0]
    assert called_url == "http://192.168.1.50:11434/api/chat"


def test_thinking_mode_is_always_disabled():
    """Qwen3 defaults to thinking mode ON, which generates a long internal
    reasoning trace before every answer - measured in real use to add
    ~140s+ per request on CPU-only hardware, and to blow past the 300s
    timeout entirely on some jobs. think=False must be sent on every
    request regardless of which model is configured - it's a harmless
    no-op for non-thinking models like llama3.1:8b, but load-bearing for
    Qwen3."""
    with patch("httpx.post", return_value=_mock_response(json.dumps({"score": 50, "reasoning": "x"}))) as mock_post:
        evaluator = OllamaEvaluator(model="qwen3:4b")
        evaluator.evaluate_match("resume", "title", "description")

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["think"] is False
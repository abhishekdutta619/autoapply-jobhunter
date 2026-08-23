from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from google.genai import errors

from app.llm.gemini_client import GeminiEvaluator


def _fake_response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(text=json.dumps(payload))


def test_evaluate_match_parses_structured_response():
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _fake_response(
        {"score": 88, "reasoning": "Strong TypeScript/Angular overlap."}
    )

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client):
        evaluator = GeminiEvaluator(api_key="test-key")
        result = evaluator.evaluate_match("resume text", "Senior Frontend Engineer", "job description")

    assert result.score == 88
    assert result.reasoning == "Strong TypeScript/Angular overlap."


def test_evaluate_match_requests_schema_constrained_json():
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _fake_response({"score": 50, "reasoning": "x"})

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client):
        evaluator = GeminiEvaluator(api_key="test-key")
        evaluator.evaluate_match("resume", "title", "description")

    _, kwargs = fake_client.models.generate_content.call_args
    config = kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema is not None
    assert config.temperature == 0
    # System prompt goes through system_instruction, not concatenated into
    # the user content - keeps the same system/user separation the other
    # three clients use.
    assert config.system_instruction is not None


def test_missing_api_key_raises_helpful_error():
    try:
        GeminiEvaluator(api_key="")
        assert False, "expected ValueError for missing API key"
    except ValueError as exc:
        # Should point at the free-tier signup, not just say "missing key".
        assert "aistudio.google.com" in str(exc)


def test_transient_429_is_retried_and_eventually_succeeds():
    """Confirmed via a real run: free-tier quota hit exactly this error
    shape. A transient rate-limit should not permanently fail the job -
    it should retry and succeed once the window clears."""
    fake_client = MagicMock()
    rate_limited = errors.ClientError(429, {"error": {"message": "quota exceeded"}}, None)
    fake_client.models.generate_content.side_effect = [
        rate_limited,
        _fake_response({"score": 70, "reasoning": "ok"}),
    ]

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client), \
         patch("tenacity.nap.time.sleep"):  # skip real backoff delay in tests
        evaluator = GeminiEvaluator(api_key="test-key")
        result = evaluator.evaluate_match("resume", "title", "description")

    assert result.score == 70
    assert fake_client.models.generate_content.call_count == 2


def test_transient_503_is_retried():
    """Confirmed via a real run: 'high demand' 503s happened repeatedly
    even within quota - these are exactly as transient as 429s."""
    fake_client = MagicMock()
    overloaded = errors.ServerError(503, {"error": {"message": "high demand"}}, None)
    fake_client.models.generate_content.side_effect = [
        overloaded,
        overloaded,
        _fake_response({"score": 55, "reasoning": "ok"}),
    ]

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client), \
         patch("tenacity.nap.time.sleep"):
        evaluator = GeminiEvaluator(api_key="test-key")
        result = evaluator.evaluate_match("resume", "title", "description")

    assert result.score == 55
    assert fake_client.models.generate_content.call_count == 3


def test_persistent_transient_error_eventually_gives_up():
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = errors.ClientError(
        429, {"error": {"message": "quota exceeded"}}, None
    )

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client), \
         patch("tenacity.nap.time.sleep"):
        evaluator = GeminiEvaluator(api_key="test-key")
        try:
            evaluator.evaluate_match("resume", "title", "description")
            assert False, "expected the persistent 429 to eventually raise"
        except errors.ClientError:
            pass

    # stop_after_attempt(4) - should have tried exactly 4 times, not looped forever.
    assert fake_client.models.generate_content.call_count == 4


def test_404_wrong_model_name_fails_fast_without_retrying():
    """Confirmed via a real run: gemini-2.5-flash 404'd for every single
    request because the model was retired for new users. This is
    permanent - retrying 4 times just wastes ~90s before failing anyway.
    Should fail on the first attempt with a message pointing at
    GEMINI_MODEL and where to check current model availability."""
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = errors.ClientError(
        404,
        {"error": {"message": "This model models/gemini-2.5-flash is no longer available"}},
        None,
    )

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client), \
         patch("tenacity.nap.time.sleep"):
        evaluator = GeminiEvaluator(api_key="test-key", model="gemini-2.5-flash")
        try:
            evaluator.evaluate_match("resume", "title", "description")
            assert False, "expected the 404 to raise"
        except errors.ClientError as exc:
            assert "GEMINI_MODEL" in str(exc)
            assert "ai.dev/rate-limit" in str(exc)

    # No retries on a permanent error - exactly one attempt.
    assert fake_client.models.generate_content.call_count == 1


def test_draft_answer_returns_plain_text_not_json():
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = SimpleNamespace(
        text="  I optimized bundle loading, cutting page load time by 30%.  "
    )

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client):
        evaluator = GeminiEvaluator(api_key="test-key")
        answer = evaluator.draft_answer(
            "Tell me about a performance win",
            "Lazy-loading rollout", "Cut page load 30%...",
            "Senior Engineer", "job description",
        )

    assert answer == "I optimized bundle loading, cutting page load time by 30%."


def test_select_dropdown_option_embeds_options_in_schema():
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _fake_response(
        {"selected_option": "5-7 years", "confidence": "high"}
    )

    with patch("app.llm.gemini_client.genai.Client", return_value=fake_client):
        evaluator = GeminiEvaluator(api_key="test-key")
        result = evaluator.select_dropdown_option(
            "Years of experience?", ["0-2 years", "3-4 years", "5-7 years", "8+ years"], "6+ years experience"
        )

    assert result.selected_option == "5-7 years"
    assert result.confidence == "high"
    _, kwargs = fake_client.models.generate_content.call_args
    schema = kwargs["config"].response_json_schema
    assert "5-7 years" in schema["properties"]["selected_option"]["enum"]
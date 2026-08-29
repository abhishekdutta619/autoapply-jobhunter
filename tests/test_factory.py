from __future__ import annotations

import pytest

from app.config import settings
from app.llm.factory import get_llm_client
from app.llm.hybrid_client import HybridEvaluator


def test_hybrid_provider_builds_ollama_and_gemini_by_default(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "hybrid")
    monkeypatch.setattr(settings, "hybrid_local_provider", "ollama")
    monkeypatch.setattr(settings, "hybrid_cloud_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")  # GeminiEvaluator requires this to construct
    monkeypatch.setattr(settings, "review_threshold", 60)
    monkeypatch.setattr(settings, "approval_threshold", 85)

    client = get_llm_client()

    assert isinstance(client, HybridEvaluator)
    from app.llm.ollama_client import OllamaEvaluator
    from app.llm.gemini_client import GeminiEvaluator
    assert isinstance(client._local, OllamaEvaluator)
    assert isinstance(client._cloud, GeminiEvaluator)
    # The whole point of building hybrid via settings instead of hardcoding -
    # confirms the actual configured thresholds reach the evaluator, not
    # some default that happens to match in this test.
    assert client._review_threshold == 60
    assert client._approval_threshold == 85


def test_hybrid_provider_respects_custom_sub_provider_choice(monkeypatch):
    """Confirms hybrid isn't hardcoded to ollama+gemini specifically - any
    two registered providers can fill the local/cloud roles."""
    monkeypatch.setattr(settings, "llm_provider", "hybrid")
    monkeypatch.setattr(settings, "hybrid_local_provider", "ollama")
    monkeypatch.setattr(settings, "hybrid_cloud_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "review_threshold", 60)
    monkeypatch.setattr(settings, "approval_threshold", 85)

    client = get_llm_client()

    from app.llm.openai_client import OpenAIEvaluator
    assert isinstance(client._cloud, OpenAIEvaluator)


def test_unknown_provider_raises_with_helpful_message(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "not-a-real-provider")

    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_client()
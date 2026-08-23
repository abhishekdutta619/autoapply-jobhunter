from __future__ import annotations

from app.config import settings
from app.llm.base import LLMClient


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "openai":
        from app.llm.openai_client import OpenAIEvaluator

        return OpenAIEvaluator(api_key=settings.openai_api_key, model=settings.openai_model)

    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_client import AnthropicEvaluator

        return AnthropicEvaluator(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )

    if settings.llm_provider == "ollama":
        from app.llm.ollama_client import OllamaEvaluator

        return OllamaEvaluator(base_url=settings.ollama_base_url, model=settings.ollama_model)

    if settings.llm_provider == "gemini":
        from app.llm.gemini_client import GeminiEvaluator

        return GeminiEvaluator(api_key=settings.gemini_api_key, model=settings.gemini_model)

    raise ValueError(
        f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Use 'openai', 'anthropic', 'ollama', or 'gemini'."
    )
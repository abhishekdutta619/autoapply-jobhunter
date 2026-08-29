from __future__ import annotations

from app.config import settings
from app.llm.base import LLMClient

_KNOWN_PROVIDERS = ("openai", "anthropic", "ollama", "gemini", "hybrid")


def _build_client(provider: str) -> LLMClient:
    """Builds a single named provider's client. Split out from
    get_llm_client() so hybrid mode can build two of these (a local one
    and a cloud one) without duplicating this if/elif chain."""
    if provider == "openai":
        from app.llm.openai_client import OpenAIEvaluator

        return OpenAIEvaluator(api_key=settings.openai_api_key, model=settings.openai_model)

    if provider == "anthropic":
        from app.llm.anthropic_client import AnthropicEvaluator

        return AnthropicEvaluator(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )

    if provider == "ollama":
        from app.llm.ollama_client import OllamaEvaluator

        return OllamaEvaluator(base_url=settings.ollama_base_url, model=settings.ollama_model)

    if provider == "gemini":
        from app.llm.gemini_client import GeminiEvaluator

        return GeminiEvaluator(api_key=settings.gemini_api_key, model=settings.gemini_model)

    raise ValueError(
        f"Unknown provider {provider!r}. Use one of: "
        f"{', '.join(p for p in _KNOWN_PROVIDERS if p != 'hybrid')}."
    )


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "hybrid":
        from app.llm.hybrid_client import HybridEvaluator

        local_client = _build_client(settings.hybrid_local_provider)
        cloud_client = _build_client(settings.hybrid_cloud_provider)
        return HybridEvaluator(
            local_client=local_client,
            cloud_client=cloud_client,
            review_threshold=settings.review_threshold,
            approval_threshold=settings.approval_threshold,
        )

    if settings.llm_provider in _KNOWN_PROVIDERS:
        return _build_client(settings.llm_provider)

    raise ValueError(f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Use one of: {', '.join(_KNOWN_PROVIDERS)}.")
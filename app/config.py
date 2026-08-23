from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./job_hunter.db")

    greenhouse_companies: list[str] = _split_csv(os.getenv("GREENHOUSE_COMPANIES"))
    lever_companies: list[str] = _split_csv(os.getenv("LEVER_COMPANIES"))
    ashby_companies: list[str] = _split_csv(os.getenv("ASHBY_COMPANIES"))

    request_delay_seconds: float = float(os.getenv("REQUEST_DELAY_SECONDS", "1.5"))

    workday_companies: list[str] = _split_csv(os.getenv("WORKDAY_COMPANIES"))
    # Workday's list endpoint doesn't include full descriptions - getting
    # one means a second request PER JOB. Worth being able to turn off for
    # a fast "what's out there" pass before committing to the slower mode.
    workday_fetch_descriptions: bool = (
        os.getenv("WORKDAY_FETCH_DESCRIPTIONS", "true").lower() == "true"
    )
    # Extra courtesy delay between those per-job detail requests, on top of
    # REQUEST_DELAY_SECONDS between companies - many Workday tenants run
    # Akamai bot management, so this source is deliberately more
    # conservative than Greenhouse/Lever/Ashby.
    workday_detail_delay_seconds: float = float(
        os.getenv("WORKDAY_DETAIL_DELAY_SECONDS", "0.5")
    )

    # --- Evaluator (Phase 2) ---
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" | "openai" | "ollama" | "gemini"

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    # Free tier (Flash-family models): no credit card, no subscription -
    # get a key at https://aistudio.google.com/apikey. Unrelated to any
    # paid consumer "Gemini Pro"/Google AI Pro subscription.
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Local, free, no API key - runs entirely on your own machine via Ollama.
    # Slower than a cloud provider and quality depends on the model you've
    # pulled; see README's "Local LLM (Ollama)" section.
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    resume_path: str = os.getenv("RESUME_PATH", "resume.md")
    # Original project spec: approve anything scoring *above* 85.
    approval_threshold: int = int(os.getenv("APPROVAL_THRESHOLD", "85"))
    # Below approval_threshold but at/above this: held as PENDING_EVALUATION
    # for a human to manually approve/reject via the dashboard, instead of
    # being auto-trashed. Set to 0 (or leave REVIEW_THRESHOLD unset and pass
    # None) to restore the original hard-cutoff behavior with no review band.
    review_threshold: int = int(os.getenv("REVIEW_THRESHOLD", "60"))
    eval_request_delay_seconds: float = float(os.getenv("EVAL_REQUEST_DELAY_SECONDS", "1.0"))

    # Optional hard constraints folded into the resume text the Evaluator
    # sends the LLM (see app/llm/prompts.py's build_constraints_section) -
    # not a schema change, so every provider picks this up automatically.
    require_remote: bool = os.getenv("REQUIRE_REMOTE", "false").strip().lower() == "true"
    # Freeform on purpose - compensation bands vary by currency/market and
    # a rigid numeric gate would be fragile. e.g. "25-30 LPA in India, or
    # globally-equivalent for remote international roles".
    target_compensation: str | None = os.getenv("TARGET_COMPENSATION") or None

    # --- Executor (Phase 3) ---
    candidate_profile_path: str = os.getenv("CANDIDATE_PROFILE_PATH", "candidate_profile.json")
    # Headed (visible) by default on purpose: a human should be watching and
    # physically present to review/submit, not running this unattended.
    executor_headless: bool = os.getenv("EXECUTOR_HEADLESS", "false").lower() == "true"

    # RAG answer drafting (optional) - used by the Executor for cover
    # letter / open-ended questions. If no story bank file exists, this
    # feature is simply skipped rather than erroring.
    story_bank_path: str = os.getenv("STORY_BANK_PATH", "story_bank.json")


settings = Settings()
from __future__ import annotations

from app.llm.base import LLMClient

_CONFIDENT_LEVELS = {"high"}


class DropdownMapper:
    """Asks the LLM to pick the best dropdown option, given the candidate's
    resume as context. Only ever returns an option the LLM was highly
    confident about and that's actually in the provided list - anything
    else comes back as None, left for the human to answer themselves.

    Does NOT check for sensitive (EEO/work-authorization) questions - that
    guard lives in the caller (app/executor/runner.py), applied before
    this class is even invoked, so the protection holds structurally
    rather than depending on every mapper implementation remembering it.
    """

    def __init__(self, llm_client: LLMClient, resume_text: str):
        self._llm_client = llm_client
        self._resume_text = resume_text

    def map_option(self, question: str, options: list[str]) -> str | None:
        if not options:
            return None

        selection = self._llm_client.select_dropdown_option(
            question=question, options=options, candidate_context=self._resume_text,
        )

        if selection.selected_option == "NONE":
            return None
        if selection.confidence not in _CONFIDENT_LEVELS:
            return None
        if selection.selected_option not in options:
            # Shouldn't happen given the schema's enum constraint, but
            # never trust a value blindly - fall back to "leave it blank".
            return None

        return selection.selected_option

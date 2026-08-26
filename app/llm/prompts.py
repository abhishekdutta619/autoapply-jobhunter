from __future__ import annotations

SYSTEM_PROMPT = (
    "You are a ruthless, no-nonsense technical recruiter. Your job is to "
    "score how well a candidate's resume matches a job description, on a "
    "scale of 1 to 100. Be strict: a generic or partial match should score "
    "well below 85. Only score 85+ if the candidate's actual experience, "
    "not just adjacent keywords, meets the role's core requirements. "
    "Base your score only on evidence in the resume - do not assume "
    "skills that aren't stated.\n\n"
    "The candidate's resume may end with a 'CANDIDATE'S PREFERENCES' "
    "section, separate from their actual experience. These are "
    "preferences, not hard requirements - skill fit must remain the "
    "dominant factor in the score either way. Weigh them as follows:\n"
    "- Work arrangement: if the candidate has a stated remote preference, "
    "treat remote as their first choice and onsite/hybrid as a real "
    "second choice, not a rejection. Apply at most a modest score "
    "reduction for onsite/hybrid postings relative to an otherwise "
    "identical remote one - never cap or floor the score based on work "
    "arrangement the way you would for an actual skill mismatch. If the "
    "posting doesn't mention work arrangement at all, don't penalize for "
    "it - there's nothing to go on.\n"
    "- Compensation: the candidate may give two different targets, one "
    "for Indian companies and one for multinational/foreign companies "
    "(MNCs). Judge from the company name and job description which "
    "category this specific posting's company falls into, and compare "
    "against the matching target - don't just apply whichever number "
    "comes first. If the posting explicitly states a range clearly below "
    "the applicable target, treat this as a moderate negative - not "
    "usually disqualifying on its own the way work-arrangement mismatch "
    "is. Most postings don't state compensation at all - don't penalize "
    "for silence, only for an explicitly stated range that's genuinely "
    "too low."
)


def build_constraints_section(
    prefer_remote: bool = False,
    target_compensation_indian: str | None = None,
    target_compensation_mnc: str | None = None,
) -> str:
    """Appended to the resume text passed into evaluate_match() - not a
    schema or signature change, so every LLMClient implementation (OpenAI,
    Anthropic, Ollama, Gemini) picks this up automatically through the
    existing `resume` parameter they already all accept identically.

    These are preferences the LLM weighs alongside skill fit, not a
    pre-filter - no job is excluded from being scored based on this.

    Returns "" if nothing is configured, so callers can always
    unconditionally do `resume_text += build_constraints_section(...)`
    without an if-check at the call site.
    """
    lines: list[str] = []
    if prefer_remote:
        lines.append(
            "- Work arrangement: candidate PREFERS fully remote roles as a "
            "first choice, and will also consider onsite/hybrid roles as a "
            "second choice. This is a preference, not a requirement - do "
            "not disqualify or heavily penalize an otherwise strong "
            "onsite/hybrid match just for not being remote."
        )

    if target_compensation_indian or target_compensation_mnc:
        comp_lines = []
        if target_compensation_indian:
            comp_lines.append(f"    - Indian company: {target_compensation_indian}")
        if target_compensation_mnc:
            comp_lines.append(f"    - Multinational/foreign company (MNC): {target_compensation_mnc}")
        lines.append(
            "- Target compensation (judge which category this posting's "
            "company falls into from its name/description):\n"
            + "\n".join(comp_lines)
        )

    if not lines:
        return ""

    return "\n\n---\nCANDIDATE'S PREFERENCES (in addition to skill fit):\n" + "\n".join(lines)


def build_user_prompt(resume: str, job_title: str, job_description: str) -> str:
    return (
        f"JOB TITLE:\n{job_title}\n\n"
        f"JOB DESCRIPTION:\n{job_description}\n\n"
        f"CANDIDATE RESUME:\n{resume}\n\n"
        "Score this match from 1 to 100 and give a one-to-two sentence "
        "reason for the score."
    )


# JSON Schema shared by both providers - OpenAI's response_format and
# Anthropic's tool input_schema both accept this shape directly.
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "description": "Match score from 1 (no fit) to 100 (perfect fit).",
        },
        "reasoning": {
            "type": "string",
            "description": "One to two sentence justification for the score.",
        },
    },
    "required": ["score", "reasoning"],
    "additionalProperties": False,
}


ANSWER_SYSTEM_PROMPT = (
    "You are helping a job candidate draft an answer to an application "
    "question. Write in first person, as the candidate. Use ONLY details "
    "present in the story provided - never invent facts, metrics, names, "
    "or outcomes that aren't there. If the story doesn't fully answer the "
    "question, write an honest answer based on what it does cover rather "
    "than fabricating the rest. Keep it concise (3-5 sentences) unless the "
    "question clearly calls for more. This is a DRAFT the candidate will "
    "review and edit before submitting, not a final answer - so prioritize "
    "accuracy to the source story over polish."
)


def build_answer_prompt(
    question: str,
    story_title: str,
    story_text: str,
    job_title: str,
    job_description: str,
) -> str:
    return (
        f"APPLICATION QUESTION:\n{question}\n\n"
        f"JOB TITLE (for tone/context only):\n{job_title}\n\n"
        f"JOB DESCRIPTION (for tone/context only):\n{job_description}\n\n"
        f"CANDIDATE'S STORY - {story_title!r}:\n{story_text}\n\n"
        "Draft the candidate's answer now, in first person, grounded only "
        "in the story above."
    )


DROPDOWN_SYSTEM_PROMPT = (
    "You are helping select the best answer to a dropdown question on a "
    "job application, based on the candidate's resume. You MUST choose "
    "exactly one of the provided options, reproduced verbatim, or the "
    "literal string 'NONE' if none of the options are a reasonable match. "
    "Never invent an option that isn't in the provided list. Rate your "
    "confidence honestly: use 'low' whenever the question is ambiguous, "
    "subjective, or you are essentially guessing - a wrong guess submitted "
    "on someone's behalf is worse than leaving it blank for them."
)


def build_dropdown_prompt(question: str, options: list[str], candidate_context: str) -> str:
    options_list = "\n".join(f"- {opt}" for opt in options)
    return (
        f"DROPDOWN QUESTION:\n{question}\n\n"
        f"AVAILABLE OPTIONS:\n{options_list}\n\n"
        f"CANDIDATE'S RESUME (for context):\n{candidate_context}\n\n"
        "Select the best option now."
    )


def build_dropdown_schema(options: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "selected_option": {"type": "string", "enum": [*options, "NONE"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["selected_option", "confidence"],
        "additionalProperties": False,
    }
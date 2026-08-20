from __future__ import annotations

SYSTEM_PROMPT = (
    "You are a ruthless, no-nonsense technical recruiter. Your job is to "
    "score how well a candidate's resume matches a job description, on a "
    "scale of 1 to 100. Be strict: a generic or partial match should score "
    "well below 85. Only score 85+ if the candidate's actual experience, "
    "not just adjacent keywords, meets the role's core requirements. "
    "Base your score only on evidence in the resume - do not assume "
    "skills that aren't stated."
)


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

from __future__ import annotations

from bs4 import BeautifulSoup


def strip_html(html: str | None) -> str:
    """Plain text from a scraped job description, for sending to an LLM.

    Every ATS source stores whatever it gave us in `description_html` -
    Greenhouse and Workday hand back real HTML (divs, inline styles, and
    sometimes embedded <script> JSON-LD blocks); Lever/Ashby sometimes
    already give plain text via a *Plain field instead. Either way, an
    LLM pays token cost for markup exactly like it does for real words,
    and gets zero signal back for it - pure overhead against whatever
    context window the model's configured with (see num_ctx in
    ollama_client.py, a hard ceiling that silently truncates rather than
    erroring if the prompt doesn't fit).

    <script>/<style> contents are removed entirely, not just their tags -
    BeautifulSoup's get_text() otherwise includes their raw contents as
    literal text, which is worse than markup overhead: actual JS/CSS/JSON
    dumped into the prompt as noise.

    Newline-joined (not space-joined) so bullet points and paragraphs stay
    visually distinct instead of running together - makes it easier for
    the model to parse a list of requirements as a list.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    return soup.get_text("\n", strip=True)
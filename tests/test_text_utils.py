from __future__ import annotations

from app.text_utils import strip_html


def test_none_input_returns_empty_string():
    assert strip_html(None) == ""


def test_empty_string_returns_empty_string():
    assert strip_html("") == ""


def test_tags_are_removed_content_remains():
    html = "<div><p>Senior Engineer role</p></div>"
    assert strip_html(html) == "Senior Engineer role"


def test_script_content_is_fully_removed_not_just_tags():
    """The failure mode BeautifulSoup's get_text() has by default: without
    explicitly decomposing <script>/<style>, their raw contents (JS, CSS,
    embedded JSON-LD) get included as literal text - worse than markup
    overhead, since it's actual code/data dumped as noise into the prompt."""
    html = '<div><p>Great role</p><script>var x = {"secret": "data"};</script></div>'
    result = strip_html(html)
    assert "Great role" in result
    assert "secret" not in result
    assert "data" not in result
    assert "var x" not in result


def test_style_content_is_fully_removed():
    html = "<div><p>Great role</p><style>.foo { color: red; }</style></div>"
    result = strip_html(html)
    assert "Great role" in result
    assert "color" not in result
    assert "red" not in result


def test_bullet_points_stay_on_separate_lines():
    """Newline-joined, not space-joined - so a <ul> of distinct
    requirements reads as a list to the model, not one run-on sentence."""
    html = "<ul><li>React experience</li><li>TypeScript proficiency</li></ul>"
    result = strip_html(html)
    lines = result.split("\n")
    assert "React experience" in lines
    assert "TypeScript proficiency" in lines


def test_inline_styles_and_classes_do_not_leak_into_text():
    html = '<div class="job-requirements" style="font-weight:400;">Content here</div>'
    result = strip_html(html)
    assert result == "Content here"
    assert "font-weight" not in result
    assert "job-requirements" not in result


def test_realistic_posting_produces_meaningfully_smaller_output():
    """Not a strict token-count assertion (that's implementation-detail
    territory), just confirms the actual point of this change: real
    savings on a realistic, moderately nested posting."""
    html = """
    <div class="job-post" style="margin: 0; padding: 20px;">
      <h1 style="font-size: 24px;">Senior Frontend Engineer</h1>
      <div class="requirements-section">
        <h2>Requirements</h2>
        <ul>
          <li>5+ years of React and TypeScript</li>
          <li>Experience with design systems</li>
          <li>Strong CSS architecture skills</li>
        </ul>
      </div>
      <script type="application/ld+json">{"@type": "JobPosting", "title": "Senior Frontend Engineer"}</script>
    </div>
    """
    result = strip_html(html)
    assert len(result) < len(html) * 0.6
    assert "JobPosting" not in result
    assert "Senior Frontend Engineer" in result
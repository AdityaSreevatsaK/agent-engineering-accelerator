import html
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pytest

from agent_accelerator import export
from agent_accelerator.cli import main
from agent_accelerator.export import (
    BrowserError,
    cell_class,
    export_report,
    find_browser,
    html_to_pdf,
    markdown_to_html,
    render_document,
    render_inline,
    split_row,
)

# Witnesses are the `s25` and `s27` entries in scripts/aea_mutate.py; each comment names the label that must fail
# the test.

ATTACK = "<script>alert(1)</script>"
ESCAPED = html.escape(ATTACK)
WHEN = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def option(argv, prefix):
    return next(arg[len(prefix) :] for arg in argv if arg.startswith(prefix))


class FakeBrowser:
    """Stands in for subprocess.run: records the call and writes (or withholds) the PDF the browser would print."""

    def __init__(self, pdf=b"%PDF-1.7 fake", raises=None, stderr="", stdout="", returncode=0):
        self.pdf, self.raises, self.stderr, self.stdout, self.returncode = pdf, raises, stderr, stdout, returncode
        self.argv = None
        self.kwargs = None
        self.page = None

    def __call__(self, argv, **kwargs):
        self.argv, self.kwargs = argv, kwargs
        profile = Path(option(argv, "--user-data-dir="))
        profile.mkdir(parents=True)
        self.page = Path(url2pathname(urlparse(argv[-1]).path)).read_text(encoding="utf-8")
        if self.raises is not None:
            raise self.raises
        if self.pdf is not None:
            Path(option(argv, "--print-to-pdf=")).write_bytes(self.pdf)
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


@pytest.fixture(autouse=True)
def no_real_browser(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a test reached subprocess.run without a FakeBrowser")

    monkeypatch.setattr(subprocess, "run", refuse)


@pytest.fixture
def browser(monkeypatch):
    fake = FakeBrowser()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "run-7.md"
    path.write_text("# Run report\n\n| case | result |\n| --- | --- |\n| a | FAIL (1/2) |\n", encoding="utf-8")
    return path


# escaping


@pytest.mark.parametrize(
    "markdown",
    [f"# {ATTACK}", ATTACK, f"- {ATTACK}", f"| h |\n| - |\n| {ATTACK} |"],
    ids=["heading", "paragraph", "bullet", "table-cell"],
)
def test_raw_html_in_any_block_is_shown_as_text(markdown):
    # Witness: s27 inline escaping removed.
    out = markdown_to_html(markdown)

    assert "<script>" not in out
    assert ESCAPED in out


def test_code_span_contents_are_escaped_and_never_emphasised():
    # Witnesses: s25 code span escaping removed; s25 code span formatted.
    assert render_inline("`<b>**x** _y_ *z*</b>`") == "<code>&lt;b&gt;**x** _y_ *z*&lt;/b&gt;</code>"


def test_quote_in_link_url_cannot_break_out_of_the_href_attribute():
    # Witness: s27 inline escaping keeps quotes.
    out = render_inline('[x](http://a/"onmouseover=alert(1))')

    assert out == '<a href="http://a/&quot;onmouseover=alert(1)">x</a>'


def test_ampersand_in_link_url_is_escaped_in_the_href():
    # Witness: s27 href unescaped.
    assert render_inline("[q](https://x.test/?a=1&b=2)") == '<a href="https://x.test/?a=1&amp;b=2">q</a>'


def test_title_and_footer_source_name_are_escaped():
    # Witness: s25 title unescaped; s25 footer source name unescaped.
    doc = render_document(f"# {ATTACK}", "a<b>.md", generated_at=WHEN)

    assert f"<title>{ESCAPED}</title>" in doc
    assert "from a&lt;b&gt;.md at" in doc
    assert "<script>" not in doc
    assert "a<b>" not in doc


# inline formatting and links


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("**bold** text", "<strong>bold</strong> text"),
        ("an *italic* word", "an <em>italic</em> word"),
        ("an _italic_ word", "an <em>italic</em> word"),
        ("snake_case_name", "snake_case_name"),
        ("a_b and c_d", "a_b and c_d"),
        ("2*3*4", "2*3*4"),
        ("run `aea run` now", "run <code>aea run</code> now"),
    ],
    ids=["bold", "star-italic", "underscore-italic", "snake-case", "two-identifiers", "arithmetic", "code"],
)
def test_inline_markdown_is_formatted_only_on_word_boundaries(markdown, expected):
    # Witness: s25 underscore italic ignores word boundaries; s25 star italic ignores word boundaries; s27 bold dropped.
    assert render_inline(markdown) == expected


@pytest.mark.parametrize(
    "url",
    ["http://x.test/a", "https://x.test/a", "mailto:me@x.test", "#failures", "runs/r1/report.md", "./a.md", "../a.md"],
    ids=["http", "https", "mailto", "anchor", "relative", "dot-relative", "parent-relative"],
)
def test_links_with_allowed_targets_become_anchors(url):
    # Witness: s25 link allow-list rejects relative.
    assert render_inline(f"[see]({url})") == f'<a href="{url}">see</a>'


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,x", "vbscript:x"],
    ids=["javascript", "javascript-mixed-case", "data", "vbscript"],
)
def test_links_with_script_or_data_targets_stay_plain_text(url):
    # Witness: s25 link allow-list widened.
    out = render_inline(f"[see]({url})")

    assert "<a" not in out
    assert out == html.escape(f"[see]({url})")


def test_underscores_in_a_link_url_are_not_turned_into_emphasis():
    # Witness: s27 link slot bypassed; s27 emphasis before links.
    assert render_inline("[x](https://x.test/_a_/)") == '<a href="https://x.test/_a_/">x</a>'


@pytest.mark.parametrize(
    "url",
    ["https://x.test/*a*/", "https://x.test/**a**/"],
    ids=["single-stars", "double-stars"],
)
def test_stars_in_a_link_url_stay_literal(url):
    # Witness: s27 link slot bypassed; s27 emphasis before links.
    assert render_inline(f"[x]({url})") == f'<a href="{url}">x</a>'


def test_emphasis_inside_a_link_label_is_rendered_inside_the_anchor():
    # Witness: s27 link label not emphasised.
    assert render_inline("[_lbl_](/p)") == '<a href="/p"><em>lbl</em></a>'


def test_bold_around_a_link_wraps_the_whole_anchor():
    # Witness: s27 bold refuses to span a link slot.
    assert render_inline("**see [x](u)**") == '<strong>see <a href="u">x</a></strong>'


def test_italic_around_a_link_wraps_the_anchor_and_keeps_underscores_in_its_url():
    # Witness: s27 link slot bypassed.
    assert render_inline("_[x](/a_b_)_") == '<em><a href="/a_b_">x</a></em>'


def test_several_links_on_one_line_are_each_restored_in_place():
    # Witness: s27 slots restored to first anchor.
    assert render_inline("[a](/x) and _[b](/y)_") == '<a href="/x">a</a> and <em><a href="/y">b</a></em>'


def test_unsafe_link_stays_plain_text_and_its_label_still_gets_emphasis():
    # Witness: s27 unsafe link hidden from emphasis.
    assert render_inline("[**x**](javascript:alert(1))") == "[<strong>x</strong>](javascript:alert(1))"


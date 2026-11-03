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


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [("a\x000\x00 b", "a0 b"), ("[x](/p) \x000\x00", '<a href="/p">x</a> 0')],
    ids=["no-link", "after-a-real-link"],
)
def test_nul_characters_in_input_are_dropped_and_cannot_forge_a_link_slot(markdown, expected):
    # Witness: s27 NUL kept.
    assert render_inline(markdown) == expected


# split_row


@pytest.mark.parametrize(
    ("line", "cells"),
    [
        ("| a | b |", ["a", "b"]),
        ("a | b", ["a", "b"]),
        ("| a | b", ["a", "b"]),
        ("a | b |", ["a", "b"]),
        ("| a \\| b | c |", ["a | b", "c"]),
        ("| a | b \\|", ["a", "b |"]),
    ],
    ids=["both-pipes", "no-pipes", "leading-only", "trailing-only", "escaped-pipe", "trailing-escaped-pipe"],
)
def test_split_row_treats_outer_pipes_as_optional_and_escaped_pipes_as_text(line, cells):
    # Witness: s25 split_row leading pipe kept; s25 split_row trailing pipe kept; s25 split_row escaped trailing pipe
    # stripped; s25 split_row splits escaped pipes.
    assert split_row(line) == cells


# tables


def test_table_alignment_markers_map_to_left_right_center_and_none():
    # Witness: s25 alignment left and right swapped; s25 alignment center lost.
    markdown = "| L | R | C | N |\n| :-- | --: | :-: | --- |\n| 1 | 2 | 3 | 4 |"
    left, right, center = (f' style="text-align: {a}"' for a in ("left", "right", "center"))

    assert markdown_to_html(markdown) == (
        "<table>\n"
        f"<thead><tr><th{left}>L</th><th{right}>R</th><th{center}>C</th><th>N</th></tr></thead>\n"
        "<tbody>\n"
        f"<tr><td{left}>1</td><td{right}>2</td><td{center}>3</td><td>4</td></tr>\n"
        "</tbody>\n"
        "</table>"
    )


def test_table_rows_are_padded_or_truncated_to_the_header_width():
    # Witness: s25 table row padding removed.
    out = markdown_to_html("| a | b | c |\n| - | - | - |\n| 1 |\n| 1 | 2 | 3 | 4 |")
    rows = re.findall(r"<tr>(.*?)</tr>", out)

    assert rows[1:] == ["<td>1</td><td></td><td></td>", "<td>1</td><td>2</td><td>3</td>"]


def test_table_ends_at_a_line_without_a_pipe():
    # Witness: s25 table swallows lines without a pipe.
    out = markdown_to_html("| a |\n| - |\n| 1 |\nafter")

    assert out.endswith("</table>\n<p>after</p>")
    assert out.count("<tr>") == 2


def test_table_ends_at_a_blank_line_and_a_later_pipe_line_is_a_paragraph():
    out = markdown_to_html("| a |\n| - |\n| 1 |\n\n| x |")

    assert out.endswith("</table>\n<p>| x |</p>")
    assert out.count("<tr>") == 2


def test_pipe_line_without_a_separator_below_is_a_paragraph():
    # Witness: s25 table needs no separator.
    assert markdown_to_html("a | b\nsee - note") == "<p>a | b<br>\nsee - note</p>"


# cell_class


@pytest.mark.parametrize(
    ("text", "css"),
    [
        ("pass (5/5)", "status-good"),
        ("OK", "status-good"),
        ("**OK**", "status-good"),
        ("passed", "status-good"),
        ("FAIL (3/5)", "status-bad"),
        ("REGRESSION", "status-bad"),
        ("error: x", "status-bad"),
        ("failed", "status-bad"),
        ("Pass rate", None),
        ("Error rate", None),
        ("passing", None),
        ("", None),
    ],
    ids=[
        "pass-tally",
        "ok",
        "bold-ok",
        "passed",
        "fail-tally",
        "regression",
        "error-reason",
        "failed",
        "pass-rate",
        "error-rate",
        "passing",
        "empty",
    ],
)
def test_cell_class_marks_status_words_alone_or_with_a_tally(text, css):
    # Witness: s25 cell_class ok dropped; s25 cell_class regression dropped; s25 cell_class word follower allowed;
    # s25 cell_class markers not stripped.
    assert cell_class(text) == css


def test_status_class_is_applied_to_body_cells_but_never_to_header_cells():
    # Witness: s25 header cells classed; s25 body cells not classed.
    out = markdown_to_html("| FAIL | x |\n| - | - |\n| FAIL (3/5) | OK |")

    assert "<th>FAIL</th>" in out
    assert '<td class="status-bad">FAIL (3/5)</td><td class="status-good">OK</td>' in out


# markdown_to_html blocks


@pytest.mark.parametrize("level", range(1, 7))
def test_headings_of_each_level_have_their_closing_hashes_stripped(level):
    # Witness: s27 heading closing hashes kept.
    marks = "#" * level

    assert markdown_to_html(f"{marks} Title {marks}") == f"<h{level}>Title</h{level}>"


def test_seven_hashes_is_a_paragraph_not_a_heading():
    assert markdown_to_html("####### x") == "<p>####### x</p>"


def test_hash_that_ends_a_word_is_kept_in_the_heading():
    # Witness: s27 heading closing hash without space.
    assert markdown_to_html("# Results for C#") == "<h1>Results for C#</h1>"


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("# Title ##  ", "<h1>Title</h1>"),
        ("## ##", "<h2></h2>"),
        ("# C# #", "<h1>C#</h1>"),
        ("# a #b", "<h1>a #b</h1>"),
        ("###   Spaced   ###", "<h3>Spaced</h3>"),
    ],
    ids=["space-after-run", "only-a-closing-run", "word-hash-then-run", "hash-starts-last-word", "wide-gaps"],
)
def test_closing_hash_run_is_stripped_only_when_it_stands_alone_at_the_end(markdown, expected):
    # Witness: s27 heading trailing space kept; s27 heading closing run needs a gap; s27 heading content greedy;
    # s27 heading not anchored at end; s27 heading single space after marker.
    assert markdown_to_html(markdown) == expected


def test_indented_continuation_line_joins_the_previous_bullet():
    # Witness: s25 bullet continuation dropped.
    assert markdown_to_html("- one\n  more\n- two") == "<ul>\n<li>one more</li>\n<li>two</li>\n</ul>"


def test_paragraph_after_a_list_closes_the_list_first():
    # Witness: s25 list not closed before paragraph.
    assert markdown_to_html("- a\nb") == "<ul>\n<li>a</li>\n</ul>\n<p>b</p>"


def test_bullet_after_a_paragraph_closes_the_paragraph_first():
    assert markdown_to_html("a\n- b\nc") == "<p>a</p>\n<ul>\n<li>b</li>\n</ul>\n<p>c</p>"


def test_heading_closes_the_open_paragraph():
    # Witness: s25 heading does not flush.
    assert markdown_to_html("a\n# H\nb") == "<p>a</p>\n<h1>H</h1>\n<p>b</p>"


def test_single_line_breaks_in_a_paragraph_become_br_and_blank_lines_split_paragraphs():
    # Witness: s25 paragraph lines joined by space.
    assert markdown_to_html("a\nb\n\nc") == "<p>a<br>\nb</p>\n<p>c</p>"


# render_document


def test_title_is_the_first_heading_with_inline_markers_removed():
    # Witness: s27 title markers kept; s27 title backtick kept.
    doc = render_document("intro\n## **Run** `x` report\n# Second", "r.md", generated_at=WHEN)

    assert "<title>Run x report</title>" in doc


@pytest.mark.parametrize("markdown", ["no heading here", "# **"], ids=["no-heading", "markers-only-heading"])
def test_title_falls_back_to_the_source_name(markdown):
    # Witness: s25 title fallback dropped; s25 title no-heading fallback dropped.
    assert "<title>r.md</title>" in render_document(markdown, "r.md", generated_at=WHEN)


def test_title_keeps_underscores_inside_identifiers():
    # Witness: s27 title strips every underscore.
    assert "<title>Report for my_agent</title>" in render_document("# Report for my_agent", "r.md", generated_at=WHEN)


@pytest.mark.parametrize(
    ("heading", "title"),
    [("snake_case_name", "snake_case_name"), ("_x_", "x"), ("__init__", "init")],
    ids=["identifier", "underscore-emphasis", "under"],
)
def test_title_drops_underscores_that_do_not_sit_between_two_letters_or_digits(heading, title):
    # Witness: s27 title strips every underscore; s27 title leading underscore kept; s27 title trailing underscore
    # kept; s27 title underscore run treated as word.
    assert f"<title>{title}</title>" in render_document(f"# {heading}", "r.md", generated_at=WHEN)


def test_footer_names_the_source_and_the_injected_time():
    # Witness: s25 generated at ignored.
    doc = render_document("# T", "report.md", generated_at=WHEN)

    assert "<footer>Generated by aea export from report.md at 2026-01-02 03:04 UTC.</footer>" in doc


def test_document_wraps_the_converted_markdown():
    markdown = "# T\n\n- a"

    assert f"<main>\n{markdown_to_html(markdown)}\n</main>" in render_document(markdown, "r.md", generated_at=WHEN)


def test_document_loads_no_scripts_stylesheets_or_network_resources():
    # Witness: s25 css imports a web font.
    doc = render_document("# T\n\ntext", "r.md", generated_at=WHEN).lower()

    for marker in ("<script", "<link", "src=", "@import", "url(", "http"):
        assert marker not in doc, marker
    assert "<style>" in doc


def test_style_sets_a_print_page_and_keeps_table_rows_together():
    # Witness: s25 css page rule dropped; s25 css row break rule dropped.
    style = render_document("# T", "r.md", generated_at=WHEN).split("<style>")[1].split("</style>")[0]

    assert re.search(r"@page\s*\{[^}]*size:", style)
    assert re.search(r"\btr\s*\{[^}]*page-break-inside:\s*avoid", style)


def style_rules(style):
    """Maps each selector of the stylesheet's top-level rules to its declaration blocks; @-rules are skipped."""
    rules = {}
    flat = re.sub(r"@[^{}]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", style)
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", flat):
        for selector in selectors.split(","):
            rules.setdefault(selector.strip(), []).append(body)
    return rules


def test_only_status_cells_are_kept_on_one_line():
    # Witness: s27 css nowrap dropped; s27 css nowrap on every cell; s27 css nowrap on bad only.
    style = render_document("# T", "r.md", generated_at=WHEN).split("<style>")[1].split("</style>")[0]
    rules = style_rules(style)
    nowrap = {sel for sel, bodies in rules.items() if any(re.search(r"white-space:\s*nowrap", b) for b in bodies)}

    assert nowrap == {"td.status-good", "td.status-bad"}
    assert rules["td"]
    assert not any("white-space" in body for body in rules["td"])


# find_browser


def only_files(monkeypatch, *paths):
    present = {Path(p) for p in paths}
    monkeypatch.setattr(Path, "is_file", lambda self: self in present)


def on_path(monkeypatch, *names):
    seen = []

    def which(name):
        seen.append(name)
        return f"/bin/{name}" if name in names else None

    monkeypatch.setattr(export.shutil, "which", which)
    return seen


def test_browser_env_override_wins_over_path(monkeypatch, tmp_path):
    # Witness: s25 browser override ignored.
    chosen = tmp_path / "my-browser.exe"
    chosen.write_bytes(b"")
    on_path(monkeypatch, "msedge", "chrome")

    assert find_browser({"AEA_BROWSER": str(chosen)}) == chosen


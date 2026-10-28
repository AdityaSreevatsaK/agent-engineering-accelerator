"""Exports an aea Markdown report to a self-contained HTML file, or to PDF through a headless Chromium browser.

The converter covers the subset the reports use: ATX headings, paragraphs, flat bullet lists, pipe tables,
bold, italic, inline code and links. All text is HTML-escaped (reports can carry dataset strings), so raw HTML
in the Markdown is shown as text, never passed through.
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

BROWSER_ENV = "AEA_BROWSER"
BROWSER_NAMES = ("msedge", "chrome", "chromium", "google-chrome", "chromium-browser")
BROWSER_TIMEOUT_S = 60

# A closing run of # counts only after whitespace (CommonMark), so "# Results for C#" keeps its #.
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s*(?<=\s)#+)?\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)")
_LINK_SLOT = re.compile("\\x00(\\d+)\\x00")
# An underscore between two letters or digits is part of a word (my_agent), not an emphasis marker.
_TITLE_MARKERS = re.compile(r"[*`]|(?<![^\W_])_(?![^\W_])")
_SAFE_URL = re.compile(r"^(https?:|mailto:|#|/|\.{0,2}/|[\w.-]+(/|$))", re.IGNORECASE)
# A status cell: the word alone or followed by a tally/reason, e.g. "FAIL (3/5)", "error: timeout"; not "Pass rate".
_STATUS = re.compile(r"^(pass|passed|ok|fail|failed|error|regression)\b(?!\s+[a-z])", re.IGNORECASE)
_GOOD = {"pass", "passed", "ok"}

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { margin: 0 auto; max-width: 1100px; padding: 24px; color: #1f2328; background: #fff;
  font: 14px/1.5 -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
h1, h2, h3, h4, h5, h6 { line-height: 1.25; margin: 1.4em 0 0.5em; page-break-after: avoid; }
h1 { font-size: 1.7em; border-bottom: 2px solid #d0d7de; padding-bottom: 0.3em; margin-top: 0; }
h2 { font-size: 1.3em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.2em; }
h3 { font-size: 1.1em; }
p, ul { margin: 0.5em 0 0.9em; }
ul { padding-left: 1.4em; }
li { margin: 0.2em 0; }
code { font: 0.9em/1.4 Consolas, "SFMono-Regular", Menlo, monospace; background: #f3f4f6; padding: 0.1em 0.3em;
  border-radius: 4px; overflow-wrap: anywhere; }
a { color: #0969da; }
table { border-collapse: collapse; width: 100%; margin: 0.6em 0 1.2em; font-size: 0.92em; }
th, td { border: 1px solid #d0d7de; padding: 5px 8px; text-align: left; vertical-align: top; }
th { background: #eef1f4; font-weight: 600; }
tbody tr:nth-child(even) { background: #f8f9fa; }
tr { page-break-inside: avoid; break-inside: avoid; }
thead { display: table-header-group; }
td.status-good { background: #e8f5e9; color: #1b5e20; }
td.status-bad { background: #fdecea; color: #a4161a; font-weight: 600; }
td.status-good, td.status-bad { white-space: nowrap; }
footer { margin-top: 2em; padding-top: 0.6em; border-top: 1px solid #d0d7de; color: #6e7781; font-size: 0.85em; }
@media print { body { padding: 0; max-width: none; } a { color: inherit; } }
"""


class BrowserError(RuntimeError):
    """No usable headless browser, or the browser failed to print the PDF."""


def render_inline(text: str) -> str:
    """Converts one line of inline Markdown to escaped HTML; code span contents are never formatted."""
    parts: list[str] = []
    last = 0
    for match in _CODE_SPAN.finditer(text):
        parts.append(_format(text[last : match.start()]))
        parts.append(f"<code>{html.escape(match.group(2).strip())}</code>")
        last = match.end()
    parts.append(_format(text[last:]))
    return "".join(parts)


def _format(text: str) -> str:
    # Anchors sit in NUL-delimited slots during the emphasis pass, so * and _ in a href stay literal.
    anchors: list[str] = []

    def stash(match: re.Match[str]) -> str:
        anchor = _link(match)
        if anchor is None:
            return match.group(0)
        anchors.append(anchor)
        return f"\x00{len(anchors) - 1}\x00"

    out = _emphasis(_LINK.sub(stash, html.escape(text.replace("\x00", ""))))
    return _LINK_SLOT.sub(lambda m: anchors[int(m.group(1))], out)


def _emphasis(text: str) -> str:
    out = _BOLD.sub(r"<strong>\1</strong>", text)
    return _ITALIC.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", out)


def _link(match: re.Match[str]) -> str | None:
    label, url = match.group(1), match.group(2)  # both already escaped
    if not _SAFE_URL.match(html.unescape(url)):
        return None  # e.g. javascript: is left as plain text
    return f'<a href="{url}">{_emphasis(label)}</a>'


def split_row(line: str) -> list[str]:
    """Splits a pipe-table row into stripped cells; a backslash-escaped pipe stays inside its cell."""
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return [cell.strip().replace("\\|", "|") for cell in _CELL_SPLIT.split(row)]


def cell_class(text: str) -> str | None:
    """CSS class for a status cell ("pass (5/5)", "FAIL (3/5)", "REGRESSION", "OK"), or None for other cells."""
    match = _STATUS.match(text.strip().strip("*_ ").strip())
    if match is None:
        return None
    return "status-good" if match.group(1).lower() in _GOOD else "status-bad"


def _alignments(separator: str) -> list[str | None]:
    aligns: list[str | None] = []
    for cell in split_row(separator):
        left, right = cell.startswith(":"), cell.endswith(":")
        aligns.append("center" if left and right else "right" if right else "left" if left else None)
    return aligns


def _table(rows: list[str]) -> str:
    header, aligns = split_row(rows[0]), _alignments(rows[1])
    width = len(header)

    def cell(tag: str, text: str, col: int) -> str:
        attrs = ""
        css = cell_class(text) if tag == "td" else None
        if css:
            attrs += f' class="{css}"'
        align = aligns[col] if col < len(aligns) else None
        if align:
            attrs += f' style="text-align: {align}"'
        return f"<{tag}{attrs}>{render_inline(text)}</{tag}>"

    lines = ["<table>", "<thead><tr>" + "".join(cell("th", t, i) for i, t in enumerate(header)) + "</tr></thead>"]
    lines.append("<tbody>")
    for raw in rows[2:]:
        cells = (split_row(raw) + [""] * width)[:width]
        lines.append("<tr>" + "".join(cell("td", t, i) for i, t in enumerate(cells)) + "</tr>")
    lines.append("</tbody>")
    lines.append("</table>")
    return "\n".join(lines)


def markdown_to_html(markdown: str) -> str:
    """Converts report Markdown to an HTML fragment (block elements only, no document wrapper)."""
    lines = markdown.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>\n".join(render_inline(p) for p in paragraph) + "</p>")
            paragraph.clear()
        if items:
            blocks.append("<ul>\n" + "\n".join(f"<li>{render_inline(i)}</li>" for i in items) + "\n</ul>")
            items.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        heading = _HEADING.match(line)
        bullet = _BULLET.match(line)
        if not line.strip():
            flush()
        elif heading:
            flush()
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{render_inline(heading.group(2))}</h{level}>")
        elif "|" in line and i + 1 < len(lines) and _TABLE_SEPARATOR.match(lines[i + 1]) and "-" in lines[i + 1]:
            flush()
            end = i + 2
            while end < len(lines) and lines[end].strip() and "|" in lines[end]:
                end += 1
            blocks.append(_table(lines[i:end]))
            i = end
            continue
        elif bullet:
            if paragraph:
                flush()
            items.append(bullet.group(1))
        elif items and line.startswith(("  ", "\t")):
            items[-1] += " " + line.strip()  # continuation of the previous bullet
        else:
            if items:
                flush()
            paragraph.append(line.strip())
        i += 1
    flush()
    return "\n".join(blocks)


def _title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        heading = _HEADING.match(line)
        if heading:
            return _TITLE_MARKERS.sub("", heading.group(2)).strip() or fallback
    return fallback


def render_document(markdown: str, source_name: str, generated_at: datetime | None = None) -> str:
    """A complete, self-contained HTML document: inline CSS, no scripts, fonts or network requests."""
    when = (generated_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    title = html.escape(_title(markdown, source_name))
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n<style>{CSS}</style>\n</head>\n<body>\n<main>\n"
        f"{markdown_to_html(markdown)}\n</main>\n"
        f"<footer>Generated by aea export from {html.escape(source_name)} at {when}.</footer>\n"
        "</body>\n</html>\n"
    )


def _install_paths(env: Mapping[str, str]) -> list[Path]:
    if sys.platform == "win32":
        roots = [env.get("PROGRAMFILES"), env.get("PROGRAMFILES(X86)"), env.get("LOCALAPPDATA")]
        relative = (
            r"Microsoft\Edge\Application\msedge.exe",
            r"Google\Chrome\Application\chrome.exe",
            r"Chromium\Application\chrome.exe",
        )
        return [Path(root) / rel for rel in relative for root in roots if root]
    if sys.platform == "darwin":
        apps = ("Microsoft Edge", "Google Chrome", "Chromium")
        return [Path(f"/Applications/{app}.app/Contents/MacOS/{app}") for app in apps]
    names = ("microsoft-edge", "google-chrome", "chromium", "chromium-browser")
    return [Path(prefix) / name for name in names for prefix in ("/usr/bin", "/snap/bin")]


def find_browser(env: Mapping[str, str] | None = None) -> Path:
    """The browser to print with: $AEA_BROWSER, then msedge/chrome/chromium on PATH, then standard install paths."""
    env = os.environ if env is None else env
    override = env.get(BROWSER_ENV)
    if override:
        path = Path(override)
        if not path.is_file():
            raise BrowserError(f"{BROWSER_ENV}={override} is not a file")
        return path
    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    for path in _install_paths(env):
        if path.is_file():
            return path
    raise BrowserError(
        f"no Chromium-based browser (Edge, Chrome or Chromium) found; set {BROWSER_ENV} to one, "
        "or use --format html and print it from any browser"
    )


def html_to_pdf(document: str, output: Path, browser: Path) -> None:
    """Prints the HTML document to output with a headless browser in a throwaway profile."""
    with tempfile.TemporaryDirectory(prefix="aea-export-") as tmp:
        page = Path(tmp) / "report.html"
        page.write_text(document, encoding="utf-8")
        pdf = Path(tmp) / "report.pdf"
        argv = [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--disable-extensions",
            "--disable-sync",
            "--disable-background-networking",
            # Managed Edge (ForceSync policy) waits for a sign-in that never comes in headless mode.
            "--disable-features=msForceBrowserSignIn",
            "--no-pdf-header-footer",
            f"--user-data-dir={Path(tmp) / 'profile'}",
            f"--print-to-pdf={pdf}",
            page.as_uri(),
        ]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=BROWSER_TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired:
            raise BrowserError(f"{browser} did not finish printing within {BROWSER_TIMEOUT_S}s") from None
        except OSError as exc:
            raise BrowserError(f"{browser} could not be started: {exc}") from None
        if not pdf.is_file() or pdf.stat().st_size == 0:
            detail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or [f"exit code {proc.returncode}"]
            raise BrowserError(f"{browser} did not write a PDF ({detail[0]})")
        shutil.move(pdf, output)


def export_report(source: Path, fmt: str, output: Path | None = None, browser: Path | None = None) -> Path:
    """Writes source (a report Markdown file) as fmt ("html" or "pdf"); returns the output path."""
    if fmt not in ("html", "pdf"):
        raise ValueError(f"unknown format {fmt!r}; use html or pdf")
    target = output or source.with_suffix(f".{fmt}")
    if target.resolve() == source.resolve():
        raise ValueError(f"output {target.as_posix()} would overwrite the input")
    document = render_document(source.read_text(encoding="utf-8"), source.name)
    if fmt == "html":
        target.write_text(document, encoding="utf-8", newline="\n")
    else:
        html_to_pdf(document, target, browser or find_browser())
    return target

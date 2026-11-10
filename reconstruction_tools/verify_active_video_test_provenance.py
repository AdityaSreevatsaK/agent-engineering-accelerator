"""Protect active AEA video-derived tests against unreviewed source drift.

This protects *reconstruction candidates* (not byte-authenticated originals).
The original video and screenshots are independent evidence; passing this
audit or ordinary pytest cannot prove original byte identity.

No runtime imports, cloud access, Inspect or LangGraph installation needed.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = ROOT / "reconstruction_drafts"
TESTS = ROOT / "tests" / "unit"

# Git blob IDs of the currently reviewed source texts, LF-normalised.
# Changing an anchored candidate requires an evidence review and an explicit
# manifest update; never change the historical assertions simply for green CI.
@dataclass(frozen=True)
class Candidate:
    git_blob: str
    lf_chars: int
    physical_lines: int
    tests: int
    video_editor_lines: int
    video_editor_chars: int
    video_eol: str


CANDIDATES = {
    "test_triage": Candidate(
        "a44c4a50907e015b33e1db71c995dc223152a3ab",
        19839, 443, 16, 444, 19847, "LF",
    ),
    "test_expense": Candidate(
        "c29989ebdc3530bfc60e7ff20313d4ea7c642b9f",
        29084, 655, 31, 656, 29737, "CRLF",
    ),
    "test_helpdesk": Candidate(
        "aade704be3bdd6e33100984e94232e10353b802f",
        19960, 453, 19, 454, 20015, "LF",
    ),
    "test_policy_rag": Candidate(
        "9ccfc238b289a18a51b62e30533c7158d6be7e01",
        18310, 415, 25, 416, 18377, "LF",
    ),
    "test_langgraph_adapter": Candidate(
        "ad2631dcf71fc08e5e3c69b9aeced72dc3b32551",
        37996, 1006, 48, 1006, 39027, "CRLF",
    ),
}

# Literal candidate artefacts preserved separately from the active code.
DIRECT_COPIES = {
    "test_triage": "test_triage_FULL_VIDEO_CANDIDATE.py",
    "test_expense": "test_expense_FULL_VIDEO_CANDIDATE.py",
}
FRAGMENT_NAME = re.compile(
    r"test_langgraph_adapter_PARTIAL_lines_(\d+)_(\d+)\.(?:py|txt)"
)


def git_blob_digest(content: str) -> str:
    """Git's SHA-1 object identity over a canonical LF-text blob."""
    data = content.encode("utf-8")
    return sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def git_blob_digest_bytes(data: bytes) -> str:
    """Git blob identity over exact stored bytes, including historical CRLF."""
    return sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def physical_line_count(content: str) -> int:
    return len(content.splitlines())


def displayed_lines(content: str) -> int:
    """Notepad++ status line count, including an empty final line after LF."""
    return content.count("\n") + 1


def editor_chars(content: str, line_ending: str) -> int:
    if line_ending not in ("LF", "CRLF"):
        raise ValueError(f"Unknown recorded line ending: {line_ending}")
    return len(content) + (content.count("\n") if line_ending == "CRLF" else 0)


def top_level_tests(text: str) -> int:
    tree = ast.parse(text, feature_version=(3, 11))
    names = [
        x.name for x in tree.body
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name.startswith("test_")
    ]
    if len(names) != len(set(names)):
        raise AssertionError("Duplicate top-level test names in recovered source")
    return len(names)


def inspect_active(name: str, *, root: Path = ROOT) -> dict[str, int]:
    if name not in CANDIDATES:
        raise KeyError(name)
    spec = CANDIDATES[name]
    path = root / "tests" / "unit" / f"{name}.py"
    content = path.read_text(encoding="utf-8")
    # Expense is intentionally checked in with original Windows CRLF bytes.
    # Other reviewed candidates use LF blobs; text read is newline-normalised.
    digest = (git_blob_digest_bytes(path.read_bytes()) if name == "test_expense"
              else git_blob_digest(content))
    if digest != spec.git_blob:
        raise AssertionError(
            f"{name}: source candidate drifted from reviewed Git blob: "
            f"expected {spec.git_blob}, got {digest}"
        )
    if len(content) != spec.lf_chars or physical_line_count(content) != spec.physical_lines:
        raise AssertionError(f"{name}: source candidate dimensions changed")
    actual_tests = top_level_tests(content)
    if actual_tests != spec.tests:
        raise AssertionError(f"{name}: expected {spec.tests} test functions, got {actual_tests}")
    if not content.endswith("\n") and name not in ("test_helpdesk", "test_policy_rag"):
        raise AssertionError(f"{name}: source candidate lost final linefeed")

    # The editor lengths come from recorded screenshots. Differences are real
    # evidence gaps, and must be shown rather than concealed or padded.
    lines_delta = displayed_lines(content) - spec.video_editor_lines
    chars_delta = editor_chars(content, spec.video_eol) - spec.video_editor_chars
    return {"test_functions": actual_tests, "lines_delta": lines_delta, "chars_delta": chars_delta}


def assemble_langgraph_fragments(*, root: Path = ROOT) -> str:
    """Prove that all 1,006 recorded reconstruction lines match the active copy."""
    draft_dir = root / "reconstruction_drafts"
    matches = []
    for path in draft_dir.iterdir():
        match = FRAGMENT_NAME.fullmatch(path.name)
        if match:
            start, end = map(int, match.groups())
            matches.append((start, end, path))
    matches.sort()
    if len(matches) != 12:
        raise AssertionError(f"LangGraph: expected 12 staged source fragments, got {len(matches)}")
    previous = 0
    pieces: list[str] = []
    for start, end, path in matches:
        if start != previous + 1 or end < start:
            raise AssertionError(f"LangGraph: fragment range gap/overlap at {path.name}")
        text = path.read_text(encoding="utf-8")
        if physical_line_count(text) != end - start + 1 or not text.endswith("\n"):
            raise AssertionError(f"LangGraph: source fragment dimension drift at {path.name}")
        pieces.append(text)
        previous = end
    if previous != 1006:
        raise AssertionError(f"LangGraph: last covered line {previous}, expected 1006")
    reconstructed = "".join(pieces)
    active = (root / "tests" / "unit" / "test_langgraph_adapter.py").read_text(encoding="utf-8")
    if reconstructed != active:
        raise AssertionError("LangGraph active file differs from preserved 12 fragment texts")
    return reconstructed


def audit_all(*, root: Path = ROOT) -> dict[str, dict[str, int]]:
    results: dict[str, dict[str, int]] = {}
    for name in CANDIDATES:
        results[name] = inspect_active(name, root=root)
    # Legacy provisional video drafts are preserved as historical evidence,
    # not overwritten when a later recording improves the active reconstruction.
    from reconstruction_tools.verify_original_video_test_candidates import validate_source
    for name, filename in DIRECT_COPIES.items():
        archive = root / "reconstruction_drafts" / filename
        if root == ROOT:
            validate_source(name)  # pins legacy SHA256 and its historical dimensions
        elif not archive.is_file():
            raise AssertionError(f"{name}: preserved provisional source draft missing")
        else:
            # Independently pin the archived bytes against the reviewed baseline.
            import hashlib
            from reconstruction_tools.verify_original_video_test_candidates import SOURCES
            original = archive.read_text(encoding="utf-8")
            if hashlib.sha256(original.encode("utf-8")).hexdigest() != SOURCES[name]["sha256"]:
                raise AssertionError(f"{name}: preserved provisional video candidate changed")
    assemble_langgraph_fragments(root=root)
    return results


def main() -> None:
    result = audit_all()
    for name, values in result.items():
        print(
            f"PINNED {name}: {values['test_functions']} tests, "
            f"editor line delta {values['lines_delta']:+d}, "
            f"editor character delta {values['chars_delta']:+d}",
            flush=True,
        )
    print(
        "PASS: 2 direct archived-copy comparisons; all 12 LangGraph fragments "
        "concatenate to active source; 5 active test source candidates pinned. "
        "NO historical original-byte fidelity claim.",
        flush=True,
    )


if __name__ == "__main__":
    main()

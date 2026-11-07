"""Audit two *provisional* original-video AEA test source candidates.

The video-derived texts are immutable draft evidence. We know the original
Notepad++ source counts and explicitly report transcribed differences rather
than padding or claiming byte-perfect fidelity.

This audit deliberately imports no reconstructed application or paid models.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "triage": {
        "file": ROOT / "reconstruction_drafts/test_triage_FULL_VIDEO_CANDIDATE.py",
        "sha256": "c23225ab0984db6aae7048f91e5b9417c8d49c68ecd469529097e3cead22a80b",
        "candidate_lines": 438,
        "candidate_lf_chars": 19400,
        "original_editor_lines": 444,
        "original_editor_chars": 19847,
        "original_eol": "LF",
        "test_functions": 16,
    },
    "expense": {
        "file": ROOT / "reconstruction_drafts/test_expense_FULL_VIDEO_CANDIDATE.py",
        "sha256": "49119a5e3ddfaf80b3452b47328c566bada39387e2a53fc78d1bbb5d58c76c88",
        "candidate_lines": 653,
        "candidate_lf_chars": 29000,
        "original_editor_lines": 656,
        "original_editor_chars": 29737,
        "original_eol": "CRLF",
        "test_functions": 31,
    },
}


def validate_source(name: str) -> tuple[str, ast.Module]:
    spec = SOURCES[name]
    path = spec["file"]
    source = path.read_text(encoding="utf-8")  # normalises Windows checkout CRLF
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest != spec["sha256"]:
        raise AssertionError(f"{name}: original test VIDEO CANDIDATE changed; visual review required")
    if len(source) != spec["candidate_lf_chars"] or len(source.splitlines()) != spec["candidate_lines"]:
        raise AssertionError(f"{name}: candidate text dimensions changed")
    if not source.endswith("\n"):
        raise AssertionError(f"{name}: recovered video candidate lost final LF")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 11))
    names = [
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    ]
    if len(names) != spec["test_functions"] or len(set(names)) != len(names):
        raise AssertionError(f"{name}: recorded test function manifest changed")
    candidate_displayed_lines = source.count("\n") + 1
    candidate_editor_chars = len(source) + (source.count("\n") if spec["original_eol"] == "CRLF" else 0)
    line_delta = candidate_displayed_lines - spec["original_editor_lines"]
    char_delta = candidate_editor_chars - spec["original_editor_chars"]
    if line_delta != (-5 if name == "triage" else -2):
        raise AssertionError(f"{name}: source line discrepancy changed: {line_delta}")
    if char_delta != (-447 if name == "triage" else -84):
        raise AssertionError(f"{name}: source character discrepancy changed: {char_delta}")
    print(
        f"CANDIDATE {name}: {len(names)} original test functions; "
        f"editor displayed lines {candidate_displayed_lines} vs {spec['original_editor_lines']} "
        f"({line_delta:+d}), editor characters {candidate_editor_chars} "
        f"vs {spec['original_editor_chars']} ({char_delta:+d}). "
        "NO original-byte fidelity claim.",
        flush=True,
    )
    return source, tree


def main() -> None:
    for name in SOURCES:
        validate_source(name)
    print("PASS: both provisional test transcripts are syntax-valid and pinned against unintended drift")


if __name__ == "__main__":
    main()

"""Evidence-based count audit for the four recovered original AEA example tests.

Run: python reconstruction_tools/audit_original_example_test_counts.py
This is a diagnostic, not a byte-identity proof or a CI quality gate.
Source metrics are from the original 8 November 2026 video evidence log.
Do not change working tests merely to force matching counts.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# (original editor lines, original editor characters, editor newline format)
EXPECTED = {
    "tests/unit/test_helpdesk.py": (454, 20015, "LF"),
    "tests/unit/test_policy_rag.py": (416, 18377, "LF"),
    "tests/unit/test_triage.py": (444, 19847, "LF"),
    "tests/unit/test_expense.py": (656, 29737, "CRLF"),
}


def editor_counts(raw: bytes, newline: str) -> tuple[int, int]:
    """Approximate Notepad++ status-bar counts from UTF-8 source.

    A trailing newline contributes an empty displayed editor line.
    Windows CRLF accounts for two characters; LF accounts for one.
    This cannot certify actual newline bytes in the historical original.
    """
    source = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    lines = source.count("\n") + 1
    characters = len(source) + (source.count("\n") if newline == "CRLF" else 0)
    return lines, characters


def observed_line_endings(raw: bytes) -> str:
    """Report actual checked-out bytes without assuming an editor convention.

    Git checkout attributes may translate line endings in a working tree.
    This is an informational provenance signal, never source authentication.
    """
    crlf = raw.count(b"\r\n")
    bare_lf = raw.count(b"\n") - crlf
    bare_cr = raw.count(b"\r") - crlf
    kinds = [name for name, count in (("CRLF", crlf), ("LF", bare_lf), ("CR", bare_cr)) if count]
    return "+".join(kinds) if kinds else "none"


def main() -> int:
    print("AEA historical video source-count audit (informational only)")
    gaps = 0
    for filename, (original_lines, original_chars, newline) in EXPECTED.items():
        path = ROOT / filename
        if not path.is_file():
            print(f"MISSING {filename}")
            gaps += 1
            continue
        raw = path.read_bytes()
        current_lines, current_chars = editor_counts(raw, newline)
        actual_eol = observed_line_endings(raw)
        dl, dc = original_lines - current_lines, original_chars - current_chars
        eol_note = "" if actual_eol == newline else " (checkout bytes differ from recording)"
        print(
            f"{filename}: original={original_lines} lines/{original_chars} chars "
            f"candidate={current_lines} lines/{current_chars} chars "
            f"gap={dl:+d} lines/{dc:+d} chars "
            f"[recorded {newline}; checked-out {actual_eol}{eol_note}]"
        )
        gaps += (dl != 0 or dc != 0)
    print(f"Files needing manual source-fidelity review: {gaps}/{len(EXPECTED)}")
    return 0  # count mismatches never fail existing CI or imply bad runtime behavior


if __name__ == "__main__":
    raise SystemExit(main())

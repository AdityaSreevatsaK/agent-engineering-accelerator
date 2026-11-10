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


def main() -> int:
    print("AEA historical video source-count audit (informational only)")
    gaps = 0
    for filename, (original_lines, original_chars, newline) in EXPECTED.items():
        path = ROOT / filename
        if not path.is_file():
            print(f"MISSING {filename}")
            gaps += 1
            continue
        current_lines, current_chars = editor_counts(path.read_bytes(), newline)
        dl, dc = original_lines - current_lines, original_chars - current_chars
        print(
            f"{filename}: original={original_lines} lines/{original_chars} chars "
            f"candidate={current_lines} lines/{current_chars} chars "
            f"gap={dl:+d} lines/{dc:+d} chars [{newline} editor convention]"
        )
        gaps += (dl != 0 or dc != 0)
    print(f"Files needing manual source-fidelity review: {gaps}/{len(EXPECTED)}")
    return 0  # count mismatches never fail existing CI or imply bad runtime behavior


if __name__ == "__main__":
    raise SystemExit(main())

"""Audit original-video conformance transcript evidence (7 November 2026).

These two files were recovered from complete Notepad++ scrolling WebM videos,
and staged at their historical paths. Character and line counts are reconciled
to the recorded Windows CRLF editor status. This does not certify historical
source-byte identity. This module is standard-library-only and offline.
"""
from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "aea_conformance_graphs.py": {
        "sha256": "30fbf40c3dca0a5244d4d0875d5264d525865f592cbbd85dc9d91c69ad4d6865",
        "chars_lf": 6051,
        "lines_physical": 190,
        "lines_editor": 191,
        "chars_editor_crlf": 6241,
    },
    "test_conformance.py": {
        "sha256": "62486a81948642493b27b37e6e4b1f40b72a1af903197237ed35045b70db24e7",
        "chars_lf": 8337,
        "lines_physical": 182,
        "lines_editor": 183,
        "chars_editor_crlf": 8519,
    },
}
EXPECTED_FACTORIES = {
    "messages_react", "create_agent_style", "ticket_triage", "functional",
    "supervisor_with_worker", "uncompiled_builder", "with_checkpointer",
    "approval_gate", "async_only", "content_blocks", "structured_dict",
    "adds_no_ai_message",
}


def validate_source(filename: str) -> tuple[str, ast.Module]:
    spec = FILES[filename]
    path = ROOT / "tests" / "conformance" / filename
    source = path.read_text(encoding="utf-8")
    checksum = sha256(source.encode("utf-8")).hexdigest()
    if checksum != spec["sha256"]:
        raise AssertionError(f"{filename}: recording-derived text changed")
    if len(source) != spec["chars_lf"]:
        raise AssertionError(f"{filename}: source length differs from reconstructed candidate")
    if not source.endswith("\n"):
        raise AssertionError(f"{filename}: recorded EOF newline missing")
    if len(source.splitlines()) != spec["lines_physical"]:
        raise AssertionError(f"{filename}: physical code line count changed")
    if source.count("\n") + 1 != spec["lines_editor"]:
        raise AssertionError(f"{filename}: Notepad++ displayed line count changed")
    if len(source) + source.count("\n") != spec["chars_editor_crlf"]:
        raise AssertionError(f"{filename}: Windows CRLF editor character count changed")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 11))
    return source, tree


def main() -> None:
    for filename in FILES:
        source, tree = validate_source(filename)
        functions = {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if filename == "aea_conformance_graphs.py":
            if not EXPECTED_FACTORIES <= functions:
                raise AssertionError(f"Graph factories missing: {EXPECTED_FACTORIES - functions}")
        else:
            tests = {name for name in functions if name.startswith("test_")}
            if len(tests) != 7:
                raise AssertionError(f"Expected seven original conformance test functions, got {tests}")
            if "@pytest.mark.slow" not in source:
                raise AssertionError("Original slow CLI conformance test marker missing")
        print(f"PASS: {filename}; {FILES[filename]['lines_editor']} editor lines, "
              f"{FILES[filename]['chars_editor_crlf']} CRLF editor characters, AST valid")
    print("Both original-video candidates pinned; byte-for-byte original equality not established.")


if __name__ == "__main__":
    main()

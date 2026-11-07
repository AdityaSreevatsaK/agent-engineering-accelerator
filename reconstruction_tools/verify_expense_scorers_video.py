"""Verify the expense scorer against the full Notepad++ source recording.

Source: user-supplied example-expense-scorer.py - video.webm (7 Nov 2026).
Recorded editor: 87 displayed lines, 4,136 Windows CRLF characters.
This audit checks a recovered *candidate*, not original-byte identity.
No network, paid models or example-agent invocation.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "expense" / "scorers.py"
SHA256_LF = "8165bd6785469ed057a44994d0cf16710bc9df58d1dd0982036520e0fc985e71"


def validate() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if source_hash != SHA256_LF:
        raise AssertionError("Expense scorer video transcription changed; investigate footage")
    if not text.endswith("\n") or len(lines) != 86 or text.count("\n") + 1 != 87:
        raise AssertionError("Expense scorer must preserve 86 physical lines and 87 editor display lines")
    if len(text) != 4050 or len(text) + text.count("\n") != 4136:
        raise AssertionError("Expense scorer differs from recorded 4,136-character CRLF editor count")
    tree = ast.parse(text, filename=str(SOURCE), feature_version=(3, 11))
    functions = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if functions != {"_to_usd", "_same", "ungrounded", "amounts_grounded"}:
        raise AssertionError(f"Recovered source's four top-level functions changed: {functions!r}")
    factory = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == "amounts_grounded")
    if len(factory.decorator_list) != 1 or not isinstance(factory.decorator_list[0], ast.Call):
        raise AssertionError("Original Inspect AI scorer decorator changed")
    if len(factory.body) != 2 or not isinstance(factory.body[0], ast.AsyncFunctionDef):
        raise AssertionError("Original asynchronous scorer implementation changed")
    if 'return "a referral approves nothing"' not in text:
        raise AssertionError("Recorded referral explanation changed")
    print(
        f"PASS: expense scorer transcript pinned {source_hash}; "
        "86 physical / 87 editor lines; 4,136 CRLF characters; AST valid. "
        "Original byte identity NOT asserted."
    )


if __name__ == "__main__":
    validate()

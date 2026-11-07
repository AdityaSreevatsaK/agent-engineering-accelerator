"""Source-evidence audit for four recovered triage/expense files (7 November).

No provider/model invocation. Python AST + stdlib TOML parse only; both
historical rules modules are missing, so callable import and E2E are deferred.
This is candidate source integrity, NOT original-byte certification.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
EXPECTATIONS = {
    "triage": {
        "config_keys": ("adapter", "agent", "input_map", "output_map"),
        "functions": {
            "lookup_invoice", "search_known_issues", "escalate_to_human",
            "_parse_label", "_call", "billing", "technical", "general",
            "_build", "build_agent", "build_reworded_agent",
            "build_live_agent", "to_input", "from_output",
        },
        "classes": {"TriageState", "SimulatedTriageModel"},
        "LF_characters_candidate": 9326,
        "physical_code_lines_candidate": 220,
        "video_editor_lines": 221,
        "video_editor_characters": 9324,
        "video_endings": "LF",
    },
    "expense": {
        "config_keys": ("adapter", "agent"),
        "functions": {
            "lookup_policy", "convert_currency", "per_diem",
            "_build", "build_agent", "build_condensed_agent",
        },
        "classes": {"SimulatedReviewModel"},
        "LF_characters_candidate": 4197,
        "physical_code_lines_candidate": 97,
        "video_editor_lines": 98,
        "video_editor_characters": 4294,
        "video_endings": "CRLF",
    },
}


def verify_example(name: str, spec: dict) -> None:
    folder = ROOT / "examples" / name
    config_file = folder / "aea.toml"
    source_file = folder / "agent.py"
    config_source = config_file.read_text(encoding="utf-8")
    settings = tomllib.loads(config_source)
    if tuple(settings) != spec["config_keys"]:
        raise AssertionError(f"{name}: config key order differs from supplied screenshot")
    if settings["adapter"] != "langgraph":
        raise AssertionError(f"{name}: screenshot adapter should be langgraph")
    if not config_source.endswith("\n"):
        raise AssertionError(f"{name}: TOML file requires final newline")

    candidate = source_file.read_text(encoding="utf-8")
    tree = ast.parse(candidate, filename=str(source_file), feature_version=(3, 11))
    if not candidate.endswith("\n"):
        raise AssertionError(f"{name}: source candidate must end in LF")
    if len(candidate) != spec["LF_characters_candidate"]:
        raise AssertionError(f"{name}: candidate source changed since the visual review")
    if len(candidate.splitlines()) != spec["physical_code_lines_candidate"]:
        raise AssertionError(f"{name}: candidate line structure changed")
    if spec["video_editor_lines"] != len(candidate.splitlines()) + 1:
        raise AssertionError(f"{name}: recorded editor displayed line count differs")

    functions = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if not spec["functions"] <= functions or not spec["classes"] <= classes:
        raise AssertionError(f"{name}: source-recorded functions/classes missing")
    for key in ("agent", "input_map", "output_map"):
        ref = settings.get(key)
        if ref is None:
            continue
        module, sep, name_of_function = ref.partition(":")
        if not sep or module != f"examples.{name}.agent":
            raise AssertionError(f"{name}: {key} reference differs from screenshot: {ref}")
        if name_of_function not in functions:
            raise AssertionError(f"{name}: {key} target absent from recovered agent")
    other_references = {
        "triage": {"examples.triage.rules", "examples.triage"},
        "expense": {"examples.expense.rules", "examples.expense"},
    }
    imported = {
        node.module for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    if not other_references[name] <= imported:
        raise AssertionError(f"{name}: missing recorded rules import contract")

    video_length_calculation = len(candidate) + (
        candidate.count("\n") if spec["video_endings"] == "CRLF" else 0
    )
    difference = video_length_calculation - spec["video_editor_characters"]
    if name == "expense" and difference:
        raise AssertionError(f"Expense video editor character count mismatch: {difference}")
    if name == "triage" and difference != 2:
        raise AssertionError(
            "Triage editor length discrepancy changed; investigate original frames"
        )
    label = (
        "EDITOR LENGTH MATCHED"
        if difference == 0
        else f"PROVISIONAL: {difference:+d} character(s) vs original screenshot"
    )
    print(
        f"PASS {name}: TOML valid, Python AST valid, reference targets declared, "
        f"source functions/classes present, displayed lines agree. {label}.",
        flush=True,
    )
    print(
        f"  Source candidate SHA256: "
        f"{hashlib.sha256(candidate.encode('utf-8')).hexdigest()}",
        flush=True,
    )


def main() -> None:
    for name, spec in EXPECTATIONS.items():
        verify_example(name, spec)
    print(
        "Neither rules.py original is present. No agent import/E2E or "
        "source-video byte fidelity certification has been claimed.",
        flush=True,
    )


if __name__ == "__main__":
    main()

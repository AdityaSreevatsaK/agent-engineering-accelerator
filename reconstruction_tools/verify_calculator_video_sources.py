"""Audit the two source files recovered from the 6 November calculator footage.

Offline, dependency-free integrity check. This validates the reconstructed
source and dataset, not original byte-for-byte provenance or the absent rules
and historical captured-log fixtures. It does not import or run the agent.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = (
    "add",
    "subtract",
    "multiply",
    "divide",
    "negative_operand",
    "decimal_operand",
    "divide_by_zero",
    "no_tool_for_chat",
    "json_output",
    "subtract_large",
)
REQUIRED_FUNCTIONS = {"calculator", "_build", "build_agent", "build_broken_agent", "build_flaky_agent"}
REQUIRED_CLASSES = {"RuleBasedModel", "FlakyModel"}


def verify(root: Path = ROOT) -> None:
    base = root / "examples" / "calculator"
    agent = base / "agent.py"
    dataset = base / "dataset.jsonl"
    if not agent.is_file() or not dataset.is_file():
        raise AssertionError("Both original calculator source and dataset reconstructions must exist")

    source = agent.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(agent), feature_version=(3, 11))
    # 101 populated physical source lines + the final Notepad++ empty line;
    # Windows CRLF editor counter from the actual video reads 'length: 4,070'.
    lines = source.splitlines()
    editor_chars = len(source) + source.count("\n")
    if len(lines) != 101 or editor_chars != 4070:
        raise AssertionError(
            f"Calculator video count mismatch: {len(lines)} physical lines, "
            f"{editor_chars} reconstructed CRLF characters; expected 101 and 4070"
        )
    functions = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    if not REQUIRED_FUNCTIONS <= functions or not REQUIRED_CLASSES <= classes:
        raise AssertionError("Original calculator constructors and model classes are missing")
    imported_rules = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "examples.calculator.rules"
        for alias in node.names
    }
    if imported_rules != {
        "BROKEN_OPERATIONS", "OPERATIONS", "SYSTEM_PROMPT", "ToolRequest",
        "answer", "calculate", "decide",
    }:
        raise AssertionError("Original calculator rules module dependencies changed")

    raw_lines = dataset.read_text(encoding="utf-8").splitlines()
    if len(raw_lines) != 10 or any(not line.strip() for line in raw_lines):
        raise AssertionError("Expected exactly ten one-case-per-line JSONL records")
    cases = [json.loads(line) for line in raw_lines]
    if tuple(case.get("id") for case in cases) != CASE_IDS:
        raise AssertionError("Recovered dataset IDs or ordering differ from screenshot")
    by_id = {case["id"]: case for case in cases}
    for case in cases:
        if not isinstance(case["input"], str) or not isinstance(case["expected_tool_calls"], list):
            raise AssertionError(f"Malformed recovered case: {case.get('id')}")
    for name, op, outcome in (
        ("add", "add", "5"), ("subtract", "sub", "5"),
        ("multiply", "mul", "42"), ("divide", "div", "2.5"),
        ("negative_operand", "add", "5"), ("decimal_operand", "mul", "6"),
        ("subtract_large", "sub", "99"),
    ):
        case = by_id[name]
        if case["expected_output"] != outcome or case["expected_tool_calls"][0]["arguments"]["op"] != op:
            raise AssertionError(f"Original outcome/operation mismatch for {name}")
    if by_id["divide_by_zero"]["output_contains"] != ["divide by zero"]:
        raise AssertionError("Original divide-by-zero expectation changed")
    if by_id["no_tool_for_chat"]["expected_tool_calls"] != []:
        raise AssertionError("Original no-tool test was changed")
    if by_id["json_output"]["expected_json_schema"]["required"] != ["result", "operation"]:
        raise AssertionError("Original JSON-output schema expectation changed")
    for name in ("json_output", "subtract_large"):
        if by_id[name]["expected_tool_calls"][0].get("match") != "subset":
            raise AssertionError(f"Original subset match missing for {name}")

    print("PASSED: restored 101-line calculator agent with video-matched 4,070 CRLF chars")
    print("PASSED: 10 screenshot-matched calculator evaluation cases and original expectations")
    print(f"Candidate agent SHA256: {hashlib.sha256(agent.read_bytes()).hexdigest()}")
    print(f"Candidate dataset SHA256: {hashlib.sha256(dataset.read_bytes()).hexdigest()}")
    if not (base / "rules.py").is_file():
        print("PENDING: original rules.py is still missing; runtime execution is not verified")


if __name__ == "__main__":
    verify()

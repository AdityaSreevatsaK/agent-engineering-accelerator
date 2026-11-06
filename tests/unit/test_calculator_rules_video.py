"""Offline contract tests for the calculator rules recovered from original footage.

This is new verification code, not a transcript of an original test file.
"""

import json
from pathlib import Path

import pytest

from examples.calculator.rules import (
    BROKEN_OPERATIONS,
    OPERATIONS,
    SYSTEM_PROMPT,
    ToolRequest,
    answer,
    calculate,
    decide,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"
RULES = ROOT / "examples" / "calculator" / "rules.py"


def test_video_recovered_rules_match_original_notepad_length_and_line_count():
    """The recorded status bar says 2030 characters and 57 displayed lines."""
    data = RULES.read_bytes()
    assert b"\r\n" not in data
    assert len(data.decode("utf-8")) == 2030
    assert data.count(b"\n") == 56  # 57 displayed lines including blank last line
    assert '"minus": "add"' in data.decode("utf-8")


@pytest.mark.parametrize(
    ("a", "b", "op", "expected"),
    [
        (2, 3, "add", 5),
        (9, 4, "sub", 5),
        (6, 7, "mul", 42),
        (10, 4, "div", 2.5),
        (-3, 8, "add", 5),
        (1.5, 4, "mul", 6),
        (100, 1, "sub", 99),
    ],
)
def test_original_calculate_arithmetic(a, b, op, expected):
    assert calculate(a, b, op) == expected


@pytest.mark.parametrize("invalid", ["mod", "", "multiply"])
def test_original_calculate_refuses_unknown_operation(invalid):
    with pytest.raises(ValueError, match="unknown operation"):
        calculate(2, 3, invalid)


def test_original_calculate_division_zero_message():
    with pytest.raises(ValueError, match="cannot divide by zero"):
        calculate(5, 0, "div")


def test_original_model_double_decision_matches_dataset_cases():
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        choice = decide(case["input"], OPERATIONS)
        if case["id"] == "no_tool_for_chat":
            assert choice == "I can only help with arithmetic."
            continue
        assert isinstance(choice, ToolRequest)
        expected = case["expected_tool_calls"][0]["arguments"]
        assert all(choice.arguments[key] == value for key, value in expected.items())


def test_original_seeded_broken_model_only_changes_subtraction():
    assert BROKEN_OPERATIONS["minus"] == "add"
    assert all(BROKEN_OPERATIONS[key] == value for key, value in OPERATIONS.items() if key != "minus")
    assert decide("What is 9 minus 4?", BROKEN_OPERATIONS) == ToolRequest({"a": 9, "b": 4, "op": "add"})
    assert calculate(9, 4, "add") == 13


def test_original_response_formatting_for_normal_and_json_questions():
    assert answer("What is 2 plus 3?", "5", failed=False) == "5"
    assert answer("What is 10 divided by 4?", "2.5", failed=False) == "2.5"
    payload = json.loads(answer("json: What is 3 times 4?", "12", failed=False))
    assert payload == {"result": 12, "operation": "mul"}
    assert answer("json: tell me a joke", "7", failed=False) == '{"result": 7, "operation": null}'


def test_original_error_response_contains_requested_signal():
    assert "divide by zero" in answer("What is 5 divided by 0?", "cannot divide by zero", failed=True)
    assert SYSTEM_PROMPT == "You are a calculator. Use the calculator tool for arithmetic."

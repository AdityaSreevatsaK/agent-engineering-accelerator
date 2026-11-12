"""Validate the calculator example dataset and its expected outcomes."""
from pathlib import Path

from agent_accelerator.dataset import dataset_sha256, load_dataset

ROOT = Path(__file__).parents[2]
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"
EXPECTED_IDS = (
    "add", "subtract", "multiply", "divide", "negative_operand",
    "decimal_operand", "divide_by_zero", "no_tool_for_chat",
    "json_output", "subtract_large",
)


def test_calculator_dataset_loads_as_ten_unique_aea_cases():
    cases = load_dataset(DATASET)
    assert len(cases) == 10
    assert tuple(c.id for c in cases) == EXPECTED_IDS
    assert len(dataset_sha256(DATASET)) == 64


def test_arithmetic_cases_retain_outputs_and_exact_tool_arguments():
    by_id = {c.id: c for c in load_dataset(DATASET)}
    for case_id, op, result in (
        ("add", "add", "5"),
        ("subtract", "sub", "5"),
        ("multiply", "mul", "42"),
        ("divide", "div", "2.5"),
        ("negative_operand", "add", "5"),
        ("decimal_operand", "mul", "6"),
    ):
        case = by_id[case_id]
        assert case.expected_output == result
        assert len(case.expected_tool_calls) == 1
        assert case.expected_tool_calls[0].name == "calculator"
        assert case.expected_tool_calls[0].arguments["op"] == op
        assert case.expected_tool_calls[0].match == "exact"


def test_no_tool_chat_and_division_by_zero_keep_distinct_check_types():
    cases = {c.id: c for c in load_dataset(DATASET)}
    chat = cases["no_tool_for_chat"]
    assert chat.expected_tool_calls == []
    assert chat.output_contains == ["arithmetic"]
    assert chat.expected_output is None
    division = cases["divide_by_zero"]
    assert division.output_contains == ["divide by zero"]
    assert division.expected_tool_calls[0].arguments == {"a": 5, "b": 0, "op": "div"}


def test_json_schema_and_large_subtraction_use_subset_tool_matching():
    cases = {c.id: c for c in load_dataset(DATASET)}
    schema = cases["json_output"].expected_json_schema
    assert schema["type"] == "object"
    assert schema["required"] == ["result", "operation"]
    assert schema["properties"]["result"] == {"type": "number"}
    assert schema["properties"]["operation"]["enum"] == ["add", "sub", "mul", "div"]
    for case_id, operation in (("json_output", "mul"), ("subtract_large", "sub")):
        case = cases[case_id]
        assert case.expected_tool_calls[0].arguments == {"op": operation}
        assert case.expected_tool_calls[0].match == "subset"
    assert cases["subtract_large"].expected_output == "99"

import hashlib

import pytest
from pydantic import ValidationError

from agent_accelerator.dataset import (
    Case,
    ExpectedToolArgs,
    ExpectedToolCall,
    case_from_metadata,
    case_to_metadata,
    dataset_sha256,
    load_dataset,
)


def test_load_dataset_skips_blank_lines(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '\n{"id":"one","input":"hello"}\n \n{"id":"two","input":"world"}\n',
        encoding="utf-8",
    )

    assert [case.id for case in load_dataset(path)] == ["one", "two"]


@pytest.mark.parametrize(
    "line",
    [
        '{invalid json}',
        '{"input":"hello"}',
        '{"id":"one"}',
        '{"id":"one","input":"hello","unexpected":true}',
    ],
    ids=["invalid-json", "missing-id", "missing-input", "unknown-field"],
)
def test_load_dataset_reports_invalid_line_with_path_and_line_number(tmp_path, line):
    path = tmp_path / "cases.jsonl"
    path.write_text('{"id":"valid","input":"ok"}\n' + line + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as error:
        load_dataset(path)

    assert f"{path}:2" in str(error.value)


def test_load_dataset_reports_unknown_expected_tool_call_field_with_path_and_line_number(
    tmp_path,
):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"valid","input":"ok"}\n'
        '{"id":"invalid","input":"x","expected_tool_calls":'
        '[{"name":"lookup","unexpected":true}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as error:
        load_dataset(path)

    assert f"{path}:2" in str(error.value)


def test_load_dataset_names_duplicate_ids(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"duplicate","input":"first"}\n'
        '{"id":"duplicate","input":"second"}\n'
        '{"id":"other","input":"third"}\n'
        '{"id":"duplicate","input":"fourth"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as error:
        load_dataset(path)

    assert "duplicate" in str(error.value)


def test_load_dataset_rejects_files_without_cases(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n \n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_dataset(path)


def test_expected_tool_call_defaults_to_exact_matching():
    assert ExpectedToolCall(name="add").match == "exact"


def test_expected_tool_call_rejects_unknown_matching_mode():
    with pytest.raises(ValidationError):
        ExpectedToolCall(name="add", match="contains")


def test_expected_tool_calls_absent_and_empty_remain_distinct(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"unchecked","input":"a"}\n{"id":"none-allowed","input":"b","expected_tool_calls":[]}\n',
        encoding="utf-8",
    )

    cases = load_dataset(path)

    assert cases[0].expected_tool_calls is None
    assert cases[1].expected_tool_calls == []


def test_dataset_sha256_hashes_file_bytes_and_changes_with_any_byte(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_bytes(b'{"id":"one","input":"hello"}\n')
    original = dataset_sha256(path)

    assert original == hashlib.sha256(path.read_bytes()).hexdigest()

    path.write_bytes(path.read_bytes() + b" ")
    assert dataset_sha256(path) != original


def test_case_metadata_round_trip():
    case = Case(
        id="tool-case",
        input="add these",
        expected_output="5",
        output_contains=["sum"],
        expected_json_schema={"type": "object"},
        expected_tool_calls=[ExpectedToolCall(name="add", arguments={"a": 2})],
        allow_extra_tool_calls=True,
        metadata={"group": "math"},
    )

    assert case_from_metadata(case_to_metadata(case)) == case


def test_dataset_sha256_treats_crlf_and_lf_line_endings_as_the_same_content(tmp_path):
    lf = tmp_path / "lf.jsonl"
    crlf = tmp_path / "crlf.jsonl"
    lf.write_bytes(b'{"id":"one","input":"a"}\n{"id":"two","input":"b"}\n')
    crlf.write_bytes(b'{"id":"one","input":"a"}\r\n{"id":"two","input":"b"}\r\n')

    assert dataset_sha256(crlf) == dataset_sha256(lf)


@pytest.mark.parametrize(
    "changed",
    [
        b'{"id":"one","input":"b"}\n{"id":"two","input":"b"}\n',
        b'{"id":"one","input":"a"}\n{"id":"two","input":"b"}',
        b'{"id":"one","input":"a"}\n{"id":"two","input":"b"}\n\n',
    ],
    ids=["one-byte-substituted", "last-byte-removed", "byte-appended"],
)
def test_dataset_sha256_changes_with_any_other_byte_change(tmp_path, changed):
    original = tmp_path / "original.jsonl"
    other = tmp_path / "other.jsonl"
    original.write_bytes(b'{"id":"one","input":"a"}\n{"id":"two","input":"b"}\n')
    other.write_bytes(changed)

    assert dataset_sha256(other) != dataset_sha256(original)


def test_output_not_contains_defaults_to_none_and_loads_from_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"unchecked","input":"a"}\n{"id":"forbidden","input":"b","output_not_contains":["Adstock","sorry"]}\n',
        encoding="utf-8",
    )

    cases = load_dataset(path)

    assert cases[0].output_not_contains is None
    assert cases[1].output_not_contains == ["Adstock", "sorry"]


def test_load_dataset_still_rejects_unknown_key_beside_output_not_contains(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"one","input":"a","output_not_contains":["x"],"output_contains_not":["y"]}\n', encoding="utf-8"
    )

    with pytest.raises(ValueError) as error:
        load_dataset(path)

    assert f"{path}:1" in str(error.value)


TRAJECTORY_FIELDS = ("expected_tools", "tool_order", "forbidden_tools", "max_tool_calls", "expected_tool_args")


def test_trajectory_fields_default_to_none():
    # Witness: s16 dataset expected_tools defaults to [] (`= []` for `= None`).
    case = Case(id="plain", input="x")

    assert {field: getattr(case, field) for field in TRAJECTORY_FIELDS} == dict.fromkeys(TRAJECTORY_FIELDS)


def test_trajectory_fields_load_from_jsonl_and_round_trip_through_metadata(tmp_path):
    # Witness: s16 dataset tool_order removed (the field line deleted, so extra="forbid" rejects the line).
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"t","input":"a","expected_tools":["lookup"],"tool_order":["lookup","refund"],'
        '"forbidden_tools":["delete"],"max_tool_calls":3,'
        '"expected_tool_args":[{"tool":"lookup","args":{"order_id":7}},{"tool":"refund"}]}\n',
        encoding="utf-8",
    )

    [case] = load_dataset(path)

    assert (case.expected_tools, case.tool_order, case.forbidden_tools, case.max_tool_calls) == (
        ["lookup"],
        ["lookup", "refund"],
        ["delete"],
        3,
    )
    assert case.expected_tool_args == [
        ExpectedToolArgs(tool="lookup", args={"order_id": 7}),
        ExpectedToolArgs(tool="refund", args={}),
    ]
    assert case_from_metadata(case_to_metadata(case)) == case


def test_max_tool_calls_accepts_zero():
    # Witness: s16 dataset max_tool_calls ge=1 rejects 0.
    assert Case(id="none", input="x", max_tool_calls=0).max_tool_calls == 0


def test_max_tool_calls_rejects_a_negative_value():
    # Witness: s16 dataset max_tool_calls unbounded (ge=0 dropped) accepts -1.
    with pytest.raises(ValidationError) as error:
        Case(id="negative", input="x", max_tool_calls=-1)

    assert error.value.errors()[0]["loc"] == ("max_tool_calls",)


def test_expected_tool_args_rejects_an_unknown_key():
    # Witness: s16 dataset ExpectedToolArgs extra ignored (extra="ignore").
    with pytest.raises(ValidationError) as error:
        ExpectedToolArgs(tool="lookup", arguments={"order_id": 7})

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_expected_tool_args_requires_tool():
    # Witness: s16 dataset ExpectedToolArgs tool optional (`tool: str = ""`).
    with pytest.raises(ValidationError) as error:
        ExpectedToolArgs(args={"order_id": 7})

    assert error.value.errors()[0]["loc"] == ("tool",)


def test_expected_tool_args_args_default_to_empty():
    # Witness: s16 dataset ExpectedToolArgs args required (default_factory dropped).
    assert ExpectedToolArgs(tool="lookup").args == {}

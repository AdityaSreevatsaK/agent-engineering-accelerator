import asyncio
import hashlib
import hmac

import pytest
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT
from inspect_ai.solver import TaskState

from agent_accelerator.dataset import Case, ExpectedToolArgs, ExpectedToolCall, case_to_metadata
from agent_accelerator.scorers import (
    case_checks,
    check_tool_calls,
    check_trajectory,
    error_type,
    output_digest,
    outputs_match,
    run_checks,
)


@pytest.mark.parametrize(
    ("expected", "actual", "matches"),
    [
        ("5", "5.0", True),
        ("2.5", "2.50", True),
        ("5", "6", False),
        ("Hello   World.", "hello world", True),
        (" hello \n world... ", "HELLO WORLD", True),
        ("hello", "hello world", False),
        ("5", "five", False),
    ],
)
def test_outputs_match_uses_numeric_or_normalised_text_comparison(expected, actual, matches):
    assert outputs_match(expected, actual) is matches


def test_tool_calls_match_expected_calls_in_order_with_optional_intervening_calls():
    expected = [
        ExpectedToolCall(name="start", arguments={"value": 1}),
        ExpectedToolCall(name="finish", arguments={"value": 2}),
    ]
    actual = [
        {"name": "start", "arguments": {"value": 1}},
        {"name": "extra", "arguments": {}},
        {"name": "finish", "arguments": {"value": 2}},
    ]

    assert check_tool_calls(Case(id="ordered", input="x", expected_tool_calls=expected), actual) is not None
    assert (
        check_tool_calls(
            Case(
                id="ordered",
                input="x",
                expected_tool_calls=expected,
                allow_extra_tool_calls=True,
            ),
            actual,
        )
        is None
    )


@pytest.mark.parametrize(
    ("expected", "actual"),
    [
        (ExpectedToolCall(name="add", arguments={"a": 1}), {"name": "subtract", "arguments": {"a": 1}}),
        (ExpectedToolCall(name="add", arguments={"a": 1}), {"name": "add", "arguments": {"a": 2}}),
        (
            ExpectedToolCall(name="add", arguments={"a": 1}, match="subset"),
            {"name": "add", "arguments": {}},
        ),
        (
            ExpectedToolCall(name="add", arguments={"a": 1}),
            {"name": "add", "arguments": {"a": 1, "b": 2}},
        ),
        (
            ExpectedToolCall(name="add", arguments={"a": 1}, match="subset"),
            {"name": "add", "arguments": {"a": 2, "b": 3}},
        ),
    ],
    ids=[
        "wrong-name",
        "wrong-value",
        "subset-missing-key",
        "exact-extra-key",
        "subset-wrong-value-with-extra-key",
    ],
)
def test_tool_call_argument_matching_rejects_mismatches(expected, actual):
    case = Case(id="mismatch", input="x", expected_tool_calls=[expected])

    assert check_tool_calls(case, [actual]) is not None


def test_tool_call_argument_matching_accepts_numeric_equivalence_and_subset_extras():
    exact = Case(
        id="exact-number",
        input="x",
        expected_tool_calls=[ExpectedToolCall(name="add", arguments={"a": 6})],
    )
    subset = Case(
        id="subset",
        input="x",
        expected_tool_calls=[ExpectedToolCall(name="add", arguments={"a": 6}, match="subset")],
    )

    assert check_tool_calls(exact, [{"name": "add", "arguments": {"a": 6.0}}]) is None
    assert check_tool_calls(subset, [{"name": "add", "arguments": {"a": 6.0, "b": 7}}]) is None


def test_tool_calls_in_wrong_order_fail():
    case = Case(
        id="wrong-order",
        input="x",
        expected_tool_calls=[
            ExpectedToolCall(name="first"),
            ExpectedToolCall(name="second"),
        ],
    )
    assert (
        check_tool_calls(
            case,
            [
                {"name": "second", "arguments": {}},
                {"name": "first", "arguments": {}},
            ],
        )
        is not None
    )



def test_unexpected_tool_calls_fail_unless_extra_calls_are_allowed():
    actual = [{"name": "extra", "arguments": {}}]
    rejects = Case(
        id="reject-extra",
        input="x",
        expected_tool_calls=[ExpectedToolCall(name="expected")],
    )
    allows = Case(
        id="allow-extra",
        input="x",
        expected_tool_calls=[ExpectedToolCall(name="expected")],
        allow_extra_tool_calls=True,
    )

    assert check_tool_calls(rejects, [{"name": "expected", "arguments": {}}, *actual]) is not None
    assert check_tool_calls(allows, [{"name": "expected", "arguments": {}}, *actual]) is None


def test_empty_expected_tool_calls_require_no_calls():
    case = Case(id="no-calls", input="x", expected_tool_calls=[])

    assert check_tool_calls(case, []) is None
    assert check_tool_calls(case, [{"name": "unexpected", "arguments": {}}]) is not None


def test_tool_call_failure_hides_expected_argument_values_by_default():
    case = Case(
        id="private",
        input="x",
        expected_tool_calls=[ExpectedToolCall(name="lookup", arguments={"secret": "expected-value"})],
    )

    message = check_tool_calls(case, [{"name": "lookup", "arguments": {"secret": "wrong"}}])

    assert message is not None
    assert "expected-value" not in message


def test_tool_call_failure_shows_expected_argument_values_when_requested():
    case = Case(
        id="visible",
        input="x",
        expected_tool_calls=[ExpectedToolCall(name="lookup", arguments={"secret": "expected-value"})],
    )

    message = check_tool_calls(
        case,
        [{"name": "lookup", "arguments": {"secret": "wrong"}}],
        show_values=True,
    )

    assert message is not None
    assert "expected-value" in message


def test_run_checks_returns_only_declared_expectations():
    case = Case(id="expected", input="x", expected_output="done")

    assert run_checks(case, "done", {}, False) == {"expected_output": None}


def test_run_checks_returns_a_key_for_each_declared_expectation_only():
    case = Case(
        id="all-expectations",
        input="x",
        expected_output='{"result":"done"}',
        output_contains=["done"],
        expected_json_schema={"type": "object"},
        expected_tool_calls=[ExpectedToolCall(name="finish")],
    )

    result = run_checks(
        case,
        '{"result":"done"}',
        {"tool_calls": [{"name": "finish", "arguments": {}}], "unrelated": True},
        False,
    )

    assert result == {
        "expected_output": None,
        "output_contains": None,
        "json_schema": None,
        "tool_calls": None,
    }


def test_run_checks_without_expectations_returns_empty_mapping():
    assert run_checks(Case(id="none", input="x"), "anything", {}, False) == {}


def test_run_checks_adds_agent_error_alongside_expectations():
    case = Case(id="error", input="x", expected_output="done")

    assert run_checks(case, "done", {"agent_error": "agent failed"}, False) == {
        "expected_output": None,
        "agent_error": "agent failed",
    }


@pytest.mark.parametrize(
    ("show_values", "expected"),
    [(False, "LookupError"), (True, "LookupError: customer dan@example.com")],
)
def test_run_checks_redacts_agent_error_message_unless_values_are_shown(show_values, expected):
    case = Case(id="error", input="x")

    result = run_checks(
        case,
        "done",
        {"agent_error": "LookupError: customer dan@example.com"},
        show_values,
    )

    assert result["agent_error"] == expected
    if not show_values:
        assert "customer dan@example.com" not in str(result)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("LookupError: customer dan@example.com", "LookupError"),
        ("RuntimeError: first: second", "RuntimeError"),
        ("agent failed", "agent failed"),
    ],
)
def test_error_type_returns_text_before_first_colon_or_whole_string(error, expected):
    assert error_type(error) == expected


def test_run_checks_treats_missing_tool_call_metadata_as_no_calls():
    case = Case(id="missing-calls", input="x", expected_tool_calls=[])

    assert run_checks(case, "", {}, False) == {"tool_calls": None}


def test_output_contains_requires_every_substring_case_insensitively():
    case = Case(id="contains", input="x", output_contains=["hello", "WORLD"])

    assert run_checks(case, "Hello there, world!", {}, False) == {"output_contains": None}
    assert run_checks(case, "Hello there", {}, False)["output_contains"] is not None


def test_json_schema_accepts_valid_json():
    case = Case(
        id="valid-json",
        input="x",
        expected_json_schema={"type": "object", "required": ["count"]},
    )

    assert run_checks(case, '{"count":3}', {}, False) == {"json_schema": None}


def test_json_schema_reports_non_json_output_as_invalid_json():
    case = Case(id="invalid-json", input="x", expected_json_schema={"type": "object"})

    message = run_checks(case, "not json", {}, False)["json_schema"]

    assert message is not None
    assert "valid JSON" in message


def test_json_schema_rejects_json_that_violates_schema():
    case = Case(
        id="wrong-schema",
        input="x",
        expected_json_schema={"type": "object", "required": ["count"]},
    )

    assert run_checks(case, "{}", {}, False)["json_schema"] is not None


def test_expected_output_failure_hides_completion_and_expected_text_by_default():
    case = Case(id="private-output", input="x", expected_output="expected secret")

    message = run_checks(case, "actual secret", {}, False)["expected_output"]

    assert message is not None
    assert "actual secret" not in message
    assert "expected secret" not in message


def test_all_run_check_failures_hide_completion_and_expected_text_by_default():
    case = Case(
        id="private-all",
        input="x",
        expected_output="expected secret",
        output_contains=["required phrase"],
        expected_json_schema={"type": "object"},
        expected_tool_calls=[ExpectedToolCall(name="expected-tool", arguments={"key": "expected secret"})],
    )
    failures = run_checks(
        case,
        "actual secret",
        {"tool_calls": [{"name": "wrong-tool", "arguments": {}}]},
        False,
    )

    for message in failures.values():
        if message is not None:
            assert "actual secret" not in message
            assert "expected secret" not in message


def test_expected_output_failure_shows_both_values_when_requested():
    case = Case(id="shown-output", input="x", expected_output="expected text")

    message = run_checks(case, "actual text", {}, True)["expected_output"]

    assert message is not None
    assert "actual text" in message
    assert "expected text" in message


def test_case_checks_returns_correct_and_marks_each_passing_check():
    case = Case(
        id="scorer-pass",
        input="x",
        expected_output="done",
        output_contains=["done"],
    )
    state = TaskState(
        model="test-model",
        sample_id=case.id,
        epoch=1,
        input=case.input,
        messages=[],
        output=ModelOutput(completion="done"),
        metadata=case_to_metadata(case),
    )

    score = asyncio.run(case_checks()(state, state.target))

    assert score.value == CORRECT
    assert score.metadata["checks"] == {
        "expected_output": True,
        "output_contains": True,
    }


def test_case_checks_returns_incorrect_and_marks_failing_check():
    case = Case(
        id="scorer-fail",
        input="x",
        expected_output="expected",
        output_contains=["present"],
    )
    state = TaskState(
        model="test-model",
        sample_id=case.id,
        epoch=1,
        input=case.input,
        messages=[],
        output=ModelOutput(completion="actual"),
        metadata=case_to_metadata(case),
    )

    score = asyncio.run(case_checks()(state, state.target))

    assert score.value == INCORRECT
    assert "expected_output" in score.explanation
    assert score.metadata["checks"] == {
        "expected_output": False,
        "output_contains": False,
    }


# The output key and value appear in the validator's absolute_path and message, never in the schema.
LEAKY_SCHEMA = {"type": "object", "additionalProperties": {"type": "integer"}}
LEAKY_OUTPUT = '{"leaky_key": "leaky_value"}'
CLOSED_SCHEMA = {"type": "object", "properties": {"allowed": {}}, "additionalProperties": False}
CLOSED_OUTPUT = '{"allowed": 1, "extra_secret": 2}'


def schema_message(schema, completion, show_values):
    case = Case(id="schema", input="x", expected_json_schema=schema)
    return run_checks(case, completion, {}, show_values)["json_schema"]


def test_redacted_schema_failure_names_only_schema_path_and_validator():
    message = schema_message(LEAKY_SCHEMA, LEAKY_OUTPUT, False)

    assert message == "schema violation at schema additionalProperties/type: type"
    assert "leaky_key" not in message
    assert "leaky_value" not in message


def test_redacted_additional_properties_failure_does_not_name_the_extra_key():
    message = schema_message(CLOSED_SCHEMA, CLOSED_OUTPUT, False)

    assert message == "schema violation at schema additionalProperties: additionalProperties"
    assert "extra_secret" not in message


def test_redacted_schema_failure_at_the_schema_root_shows_root():
    # A boolean schema is the only way to fail with an empty schema path; Case types it as a dict.
    case = Case(id="schema", input="x", expected_json_schema={}).model_copy(update={"expected_json_schema": False})

    message = run_checks(case, '{"leaky_key": 1}', {}, False)["json_schema"]

    assert message == "schema violation at schema <root>: None"
    assert "leaky_key" not in message


def test_shown_schema_failure_includes_output_path_and_validator_message():
    message = schema_message(LEAKY_SCHEMA, LEAKY_OUTPUT, True)

    assert message == (
        "schema violation at leaky_key (schema additionalProperties/type): type: 'leaky_value' is not of type 'integer'"
    )


def test_shown_schema_failure_at_the_output_root_shows_root():
    message = schema_message({"type": "object"}, "[]", True)

    assert message == "schema violation at <root> (schema type): type: [] is not of type 'object'"


@pytest.mark.parametrize("show_values", [False, True])
def test_invalid_json_message_is_the_same_whether_or_not_values_are_shown(show_values):
    assert schema_message(LEAKY_SCHEMA, "not json", show_values) == "output is not valid JSON"


# output_not_contains


def test_output_not_contains_is_not_checked_when_absent():
    case = Case(id="unchecked", input="x", output_contains=["done"])

    assert "output_not_contains" not in run_checks(case, "done, sorry", {}, False)


def test_empty_output_not_contains_passes():
    case = Case(id="empty", input="x", output_not_contains=[])

    assert run_checks(case, "anything at all", {}, False) == {"output_not_contains": None}


@pytest.mark.parametrize(
    ("forbidden", "completion"),
    [("Adstock", "the adstock decays"), ("adstock", "The ADSTOCK decays")],
    ids=["forbidden-capitalised", "output-capitalised"],
)
def test_output_not_contains_matches_case_insensitively(forbidden, completion):
    case = Case(id="forbidden", input="x", output_not_contains=[forbidden])

    assert run_checks(case, completion, {}, False) == {
        "output_not_contains": "output contains 1 forbidden substring(s)"
    }


def test_output_not_contains_passes_when_no_forbidden_substring_appears():
    case = Case(id="clean", input="x", output_not_contains=["adstock", "sorry"])

    assert run_checks(case, "Spend rose 5%.", {}, False) == {"output_not_contains": None}


def test_output_not_contains_counts_each_forbidden_entry_found_once():
    case = Case(id="count", input="x", output_not_contains=["adstock", "sorry", "absent"])

    result = run_checks(case, "Sorry, adstock and more adstock, sorry.", {}, False)

    assert result["output_not_contains"] == "output contains 2 forbidden substring(s)"


def test_output_not_contains_and_output_contains_can_both_fail_on_one_case():
    case = Case(id="both", input="x", output_contains=["required"], output_not_contains=["sorry"])

    result = run_checks(case, "sorry", {}, False)

    assert result == {
        "output_contains": "output missing 1 required substring(s)",
        "output_not_contains": "output contains 1 forbidden substring(s)",
    }


def test_output_not_contains_failure_hides_forbidden_strings_by_default():
    case = Case(id="hidden", input="x", output_not_contains=["Adstock", "carryover"])

    message = run_checks(case, "adstock and carryover", {}, False)["output_not_contains"]

    assert message == "output contains 2 forbidden substring(s)"
    assert "adstock" not in message.casefold()
    assert "carryover" not in message


def test_output_not_contains_failure_lists_only_found_strings_when_values_are_shown():
    case = Case(id="shown", input="x", output_not_contains=["Adstock", "absent", "sorry"])

    message = run_checks(case, "sorry, the adstock", {}, True)["output_not_contains"]

    assert message == "output contains 2 forbidden substring(s): ['Adstock', 'sorry']"


# Trajectory checks (spec section 15). Calls are the adapters' normalised {"name", "arguments"} dicts.

SENTINEL = "order-sentinel-4417"  # an argument value that must never reach a redacted message


def call(name, **arguments):
    return {"name": name, "arguments": arguments}


def trajectory(actual, show_values=False, **fields):
    return check_trajectory(Case(id="trajectory", input="x", **fields), actual, show_values)


@pytest.mark.parametrize(
    ("fields", "actual"),
    [
        ({"expected_tools": ["lookup", "refund"]}, [call("refund"), call("lookup"), call("lookup")]),
        ({"expected_tools": []}, []),
        ({"tool_order": ["lookup", "refund"]}, [call("lookup"), call("audit"), call("refund")]),
        ({"tool_order": []}, []),
        ({"tool_order": ["lookup", "lookup"]}, [call("lookup"), call("audit"), call("lookup")]),
        ({"forbidden_tools": ["delete"]}, [call("lookup"), call("refund")]),
        ({"max_tool_calls": 2}, [call("lookup"), call("refund")]),
        ({"max_tool_calls": 0}, []),
    ],
    ids=[
        "expected-tools-all-called-with-repeats",
        "expected-tools-empty",
        "order-with-calls-interleaved",
        "order-empty",
        "order-repeated-name-with-two-calls",
        "forbidden-none-called-unrelated-ignored",
        "max-equal-to-limit",
        "max-zero-with-no-calls",
    ],
)
def test_trajectory_check_passes_under_its_own_key_when_satisfied(fields, actual):
    # Witnesses: s16 expected_tools inverted (`t in names`) fails expected-tools-all-called-with-repeats;
    # s16 expected_tools empty skipped (`if case.expected_tools:`) drops the key for expected-tools-empty;
    # s16 max uses >= fails max-equal-to-limit and max-zero-with-no-calls.
    assert trajectory(actual, **fields) == {next(iter(fields)): None}


def test_expected_tools_failure_lists_only_missing_names_each_once():
    # Witnesses: s16 expected_tools lists all (every expected name reported once any is missing);
    # s16 expected_tools duplicates (drop dict.fromkeys, so 'audit' appears twice).
    result = trajectory([call("lookup")], expected_tools=["lookup", "audit", "refund", "audit"])

    assert result == {"expected_tools": "tool(s) never called: ['audit', 'refund']"}


@pytest.mark.parametrize(
    ("order", "actual", "message"),
    [
        (["lookup", "refund"], [call("refund"), call("lookup")], "step 2 of 2 'refund' not found in order"),
        (["lookup", "lookup"], [call("lookup")], "step 2 of 2 'lookup' not found in order"),
        (["lookup", "audit", "refund"], [call("refund")], "step 1 of 3 'lookup' not found in order"),
    ],
    ids=["reversed", "repeated-name-needs-two-calls", "first-unmatched-step-is-reported"],
)
def test_tool_order_failure_names_first_unmatched_step_position_and_total(order, actual, message):
    # Witnesses: s16 order plain membership (iterator recreated per step) passes reversed and repeated;
    # s16 order no break (a later failing step overwrites the first) reports step 3 of 3;
    # s16 order position 0-based reports step 1 of 2.
    assert trajectory(actual, tool_order=order) == {"tool_order": message}


def test_forbidden_tools_failure_lists_only_forbidden_names_called_each_once():
    # Witnesses: s16 forbidden inverted reports ['refund']; s16 forbidden first only reports ['delete'];
    # s16 forbidden duplicates (drop dict.fromkeys) reports 'delete' twice.
    actual = [call("delete"), call("lookup"), call("audit"), call("delete")]

    result = trajectory(actual, forbidden_tools=["delete", "refund", "audit", "delete"])

    assert result == {"forbidden_tools": "forbidden tool(s) called: ['delete', 'audit']"}


@pytest.mark.parametrize(
    ("limit", "count", "message"),
    [(2, 3, "3 tool calls, at most 2 allowed"), (0, 1, "1 tool calls, at most 0 allowed")],
    ids=["one-over", "zero-limit-one-call"],
)
def test_max_tool_calls_fails_one_over_the_limit_with_count_and_limit(limit, count, message):
    # Witness: s16 max uses len - 1 (3 - 1 > 2 is false, so one-over passes).
    actual = [call(f"tool{i}") for i in range(count)]

    assert trajectory(actual, max_tool_calls=limit) == {"max_tool_calls": message}


def args_spec(tool, **args):
    return ExpectedToolArgs(tool=tool, args=args)


@pytest.mark.parametrize(
    ("specs", "actual"),
    [
        ([args_spec("lookup", order_id=7)], [call("lookup", order_id=7, verbose=True)]),
        ([args_spec("lookup", order_id=7)], [call("lookup", order_id=1), call("lookup", order_id=7)]),
        ([args_spec("lookup")], [call("lookup", order_id=1)]),
    ],
    ids=["extra-actual-keys-allowed", "any-one-call-of-the-tool-suffices", "empty-args-needs-only-a-call"],
)
def test_expected_tool_args_passes_on_a_subset_match(specs, actual):
    # Witnesses: s16 args exact fails extra-actual-keys-allowed and empty-args-needs-only-a-call;
    # s16 args all calls (`all` for `any`) fails any-one-call-of-the-tool-suffices.
    assert trajectory(actual, expected_tool_args=specs) == {"expected_tool_args": None}


@pytest.mark.parametrize(
    ("specs", "actual", "message"),
    [
        ([args_spec("lookup", order_id=7)], [call("lookup", verbose=True)], "lookup(keys ['order_id'])"),
        ([args_spec("lookup", order_id=7)], [call("lookup", order_id=8)], "lookup(keys ['order_id'])"),
        ([args_spec("lookup", order_id=7)], [call("refund", order_id=7)], "lookup(keys ['order_id'])"),
        ([args_spec("lookup")], [call("refund")], "lookup(keys [])"),
    ],
    ids=["missing-key", "different-value", "matching-args-on-another-tool", "empty-args-tool-never-called"],
)
def test_expected_tool_args_fails_when_no_call_of_that_tool_matches(specs, actual, message):
    # Witness: s16 args ignore tool name passes matching-args-on-another-tool and empty-args-tool-never-called.
    assert trajectory(actual, expected_tool_args=specs) == {"expected_tool_args": f"no call matching: {message}"}


def test_expected_tool_args_failure_lists_only_unmatched_specs_in_dataset_order():
    # Witness: s16 args sorted specs (specs iterated by tool name) puts 'cancel' before 'zap'.
    specs = [args_spec("zap", force=True), args_spec("lookup"), args_spec("cancel", reason="late")]

    result = trajectory([call("lookup")], expected_tool_args=specs)

    assert result == {"expected_tool_args": "no call matching: zap(keys ['force']), cancel(keys ['reason'])"}


def test_expected_tool_args_failure_names_tool_and_sorted_keys_but_no_value_by_default():
    # Witness: s16 args values always shown (`if show_values` replaced by `if True`).
    specs = [args_spec("lookup", zeta=SENTINEL, alpha=1)]

    message = trajectory([call("refund")], expected_tool_args=specs)["expected_tool_args"]

    assert message == "no call matching: lookup(keys ['alpha', 'zeta'])"
    assert SENTINEL not in message


def test_expected_tool_args_failure_shows_expected_values_when_requested():
    # Witness: s16 args values never shown (`if show_values` replaced by `if False`).
    specs = [args_spec("lookup", zeta=SENTINEL, alpha=1)]

    message = trajectory([call("refund")], True, expected_tool_args=specs)["expected_tool_args"]

    assert message == f"no call matching: lookup{{'zeta': '{SENTINEL}', 'alpha': 1}}"


@pytest.mark.parametrize("show_values", [False, True])
def test_other_trajectory_failures_never_contain_argument_values(show_values):
    # Witness: s16 forbidden lists calls (reports the called entries, arguments included, instead of names).
    actual = [call("delete", order_id=SENTINEL), call("delete", order_id=SENTINEL)]

    result = trajectory(
        actual,
        show_values,
        expected_tools=["lookup"],
        tool_order=["lookup"],
        forbidden_tools=["delete"],
        max_tool_calls=1,
    )

    assert set(result) == {"expected_tools", "tool_order", "forbidden_tools", "max_tool_calls"}
    assert all(result.values())
    assert SENTINEL not in str(result)


def test_case_checks_reports_each_failing_trajectory_check_on_its_own():
    # Witnesses: s16 run_checks skips trajectory; s16 run_checks trajectory only with expected_tool_calls.
    case = Case(
        id="all-fail",
        input="x",
        expected_tools=["lookup"],
        tool_order=["lookup"],
        forbidden_tools=["delete"],
        max_tool_calls=0,
        expected_tool_args=[args_spec("lookup")],
    )
    state = TaskState(
        model="test-model",
        sample_id=case.id,
        epoch=1,
        input=case.input,
        messages=[],
        output=ModelOutput(completion="done"),
        metadata={**case_to_metadata(case), "tool_calls": [call("delete")]},
    )

    score = asyncio.run(case_checks()(state, state.target))

    assert score.value == INCORRECT
    assert score.explanation.split("; ") == [
        "expected_tools: tool(s) never called: ['lookup']",
        "tool_order: step 1 of 1 'lookup' not found in order",
        "forbidden_tools: forbidden tool(s) called: ['delete']",
        "max_tool_calls: 1 tool calls, at most 0 allowed",
        "expected_tool_args: no call matching: lookup(keys [])",
    ]
    assert score.metadata["checks"] == dict.fromkeys(
        ["expected_tools", "tool_order", "forbidden_tools", "max_tool_calls", "expected_tool_args"], False
    )


def test_a_failing_trajectory_check_does_not_mask_a_passing_one_or_expected_tool_calls():
    # Witness: s16 run_checks trajectory only without expected_tool_calls (moved into an `else:`) drops both keys.
    case = Case(
        id="mixed",
        input="x",
        expected_tool_calls=[ExpectedToolCall(name="delete")],
        forbidden_tools=["delete"],
        max_tool_calls=1,
    )

    assert run_checks(case, "", {"tool_calls": [call("delete")]}, False) == {
        "tool_calls": None,
        "forbidden_tools": "forbidden tool(s) called: ['delete']",
        "max_tool_calls": None,
    }


def test_run_checks_treats_missing_tool_call_metadata_as_no_calls_for_trajectory_checks():
    # Witness: s16 trajectory requires tool_calls key (`metadata["tool_calls"]` raises KeyError).
    case = Case(id="no-calls", input="x", expected_tools=["lookup"], forbidden_tools=["delete"], max_tool_calls=0)

    assert run_checks(case, "", {}, False) == {
        "expected_tools": "tool(s) never called: ['lookup']",
        "forbidden_tools": None,
        "max_tool_calls": None,
    }


def score_for(metadata):
    case = Case(id="count", input="x")
    state = TaskState(
        model="test-model",
        sample_id=case.id,
        epoch=1,
        input=case.input,
        messages=[],
        output=ModelOutput(completion="done"),
        metadata={**case_to_metadata(case), **metadata},
    )
    return asyncio.run(case_checks()(state, state.target))


@pytest.mark.parametrize(
    ("metadata", "count"),
    [
        ({"tool_calls": [call("lookup"), call("lookup", order_id=1), call("refund")]}, 3),
        ({"tool_calls": []}, 0),
        ({}, None),
    ],
    ids=["three-calls", "recorded-empty-is-zero", "unrecorded-is-none"],
)
def test_case_checks_records_tool_call_count_and_none_when_the_adapter_recorded_none(metadata, count):
    # Witnesses: s16 count always zero (`len([])`) fails three-calls; s16 count missing is zero (`else 0`)
    # fails unrecorded-is-none.
    assert score_for(metadata).metadata["tool_call_count"] == count


def test_output_digest_is_the_first_16_hex_chars_of_hmac_sha256_of_the_output():
    # Worked independently with the standard library. Witness: s22 digest unkeyed sha256, s22 digest length 32.
    key = bytes(range(32))

    assert output_digest(key, "5") == hmac.new(key, b"5", hashlib.sha256).hexdigest()[:16]
    assert len(output_digest(key, "5")) == 16


def test_output_digest_differs_for_different_outputs_and_for_different_keys():
    first, second = bytes(32), bytes([1] * 32)

    assert output_digest(first, "5") == output_digest(first, "5")
    assert output_digest(first, "5") != output_digest(first, "6")
    assert output_digest(first, "5") != output_digest(second, "5")


def scored(scorer, completion, case_id="digest"):
    case = Case(id=case_id, input=f"input of {case_id}")
    state = TaskState(
        model="test-model",
        sample_id=case.id,
        epoch=1,
        input=case.input,
        messages=[],
        output=ModelOutput(completion=completion),
        metadata=case_to_metadata(case),
    )
    return asyncio.run(scorer(state, state.target))


def digest_of(scorer, completion, case_id="digest"):
    return scored(scorer, completion, case_id).metadata["output_digest"]


def test_case_checks_digest_is_equal_for_equal_outputs_within_one_scorer_instance():
    # Different cases with the same output share a digest: it is keyed on the output alone.
    # Witnesses: s22 digest key per scorer call, s22 digest over the input.
    scorer = case_checks()

    assert digest_of(scorer, "5", "a") == digest_of(scorer, "5", "b")
    assert digest_of(scorer, "5", "a") != digest_of(scorer, "6", "a")


def test_case_checks_instances_use_different_digest_keys():
    # Two runs cannot match digests. Witness: s22 digest fixed key.
    assert digest_of(case_checks(), "5") != digest_of(case_checks(), "5")


def test_case_checks_digest_is_not_the_unkeyed_hash_of_the_output():
    # A short output must not be recoverable by hashing guesses.
    digest = digest_of(case_checks(), "5")

    assert len(digest) == 16
    assert int(digest, 16) >= 0
    assert digest != hashlib.sha256(b"5").hexdigest()[:16]


def test_case_checks_never_stores_its_digest_key_in_the_score(monkeypatch):
    # With the key pinned, the digest is the HMAC under that key, so the pinned key is the one in use. Changing the
    # key then changes the digest and nothing else in the score: any stored form of the key (hex, bytes, ints) differs.
    # Witness: s22 digest key stored, s22 digest key stored as ints.
    key_a, key_b = bytes(range(100, 132)), bytes(range(200, 232))
    scores = {}
    for key in (key_a, key_b):
        monkeypatch.setattr("agent_accelerator.scorers.secrets.token_bytes", lambda n, key=key: key)
        scores[key] = scored(case_checks(), "5")

    assert scores[key_a].metadata["output_digest"] == hmac.new(key_a, b"5", hashlib.sha256).hexdigest()[:16]
    assert scores[key_b].metadata["output_digest"] == hmac.new(key_b, b"5", hashlib.sha256).hexdigest()[:16]
    without_digest = [
        {**s.model_dump(), "metadata": {k: v for k, v in s.metadata.items() if k != "output_digest"}}
        for s in scores.values()
    ]
    assert without_digest[0] == without_digest[1]

import json
import re
from collections import Counter
from datetime import date

import pytest
from inspect_ai.scorer import Score

from agent_accelerator.dataset import Case, ExpectedToolCall
from agent_accelerator.tool_metrics import (
    CaseToolUse,
    case_tool_use,
    expected_tool_names,
    redundant_calls,
    run_tool_use,
    score_metadata,
    selection,
    tool_use_lines,
)

SECRET = "SECRET-ARGUMENT-0xA11CE"
HEADER = "## Tool use (informational)"


def call(name, **arguments):
    return {"name": name, "arguments": arguments}


def case(**fields):
    return Case(id="c", input="x", **fields)


def epoch(**metadata):
    return Score(value="C", metadata=metadata)


def use(calls=(1,), *, by_tool=None, results=0, errors=0, redundant=0, precision=None, recall=None):
    return CaseToolUse(
        calls_per_epoch=tuple(calls),
        by_tool={"t": sum(calls)} if by_tool is None else by_tool,
        results=results,
        errors=errors,
        redundant=redundant,
        precision=precision,
        recall=recall,
    )


def bullet(lines, label):
    return next(line for line in lines if line.startswith(f"- {label}: "))


def table_rows(lines):
    start = lines.index("| Tool | Calls | Share |") + 2
    return lines[start:]


# redundant_calls


@pytest.mark.parametrize(
    ("calls", "expected"),
    [
        ([call("a", x=1), call("a", x=1)], 1),
        ([call("a", x=1, y=2), call("a", y=2, x=1)], 1),
        ([call("a", q={"m": 1, "n": 2}), call("a", q={"n": 2, "m": 1})], 1),
        ([call("a", x=1), call("a", x=2)], 0),
        ([call("a", x=1), call("b", x=1)], 0),
        ([call("a", x=1), call("a", x="1")], 0),
        ([call("a", x=1), call("b"), call("a", x=1), call("a", x=1)], 2),
        ([call("a", day=date(2026, 1, 2)), call("a", day=date(2026, 1, 2))], 1),
        ([], 0),
    ],
    ids=[
        "same-name-and-args",
        "key-order-irrelevant",
        "nested-key-order-irrelevant",
        "different-args",
        "different-name",
        "different-arg-type",
        "each-later-repeat-counts-once",
        "non-json-argument",
        "no-calls",
    ],
)
def test_redundant_calls_count_repeats_of_an_earlier_call_with_the_same_name_and_arguments(calls, expected):
    # Witnesses: s21 redundant key order matters (sort_keys=False) fails both key-order ids; s21 redundant name
    # ignored fails different-name; s21 redundant args ignored fails different-args; s21 redundant first call
    # counted (add before the check) fails every id with calls; s21 redundant non-JSON args (default=str dropped)
    # raises TypeError for non-json-argument.
    assert redundant_calls(calls) == expected


# expected_tool_names

@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, None),
        ({"expected_tool_calls": [ExpectedToolCall(name="a"), ExpectedToolCall(name="b")]}, {"a", "b"}),
        ({"expected_tools": ["c"]}, {"c"}),
        ({"expected_tool_calls": [ExpectedToolCall(name="a")], "expected_tools": ["a", "c"]}, {"a", "c"}),
        ({"expected_tool_calls": []}, set()),
        ({"expected_tools": [], "forbidden_tools": ["z"], "tool_order": ["y"]}, set()),
    ],
    ids=["neither", "calls-only", "tools-only", "union", "no-tool-may-be-called", "other-trajectory-fields-ignored"],
)
def test_expected_tool_names_are_the_union_of_both_declarations_or_none_when_neither_is_declared(fields, expected):
    # Witnesses: s21 expected either declared ('and' to 'or') fails calls-only and tools-only; s21 expected
    # tools dropped fails tools-only and union.
    assert expected_tool_names(case(**fields)) == expected



# selection

@pytest.mark.parametrize(
    ("called", "expected", "result"),
    [
        (["a", "a", "b"], {"a"}, (0.5, 1.0)),
        (["a"], {"a", "b"}, (1.0, 0.5)),
        (["c"], {"a"}, (0.0, 0.0)),
        ([], {"a"}, (None, 0.0)),
        (["a"], set(), (0.0, None)),
        ([], set(), (None, None)),
    ],
    ids=["duplicates-count-once", "partial-recall", "all-wrong", "no-calls", "nothing-expected", "both-empty"],
)
def test_selection_scores_distinct_called_tools_against_the_expected_set(called, expected, result):
    # Witnesses: s21 precision over all calls (len(list(called))) gives 1/3 for duplicates-count-once; s21 precision
    # and recall swapped fails partial-recall; s21 precision zero when no calls ('else 0.0') fails no-calls.
    assert selection(called, expected) == result



# score_metadata


def test_score_metadata_is_empty_when_the_adapter_recorded_no_calls_list():
    # Witness: s21 metadata for missing calls ('if calls is None' dropped) raises TypeError iterating None.
    assert score_metadata(case(expected_tools=["a"]), None, [True]) == {}


def test_score_metadata_records_names_outcomes_redundancy_and_selection_only():
    # Witnesses: s21 unknown outcome counted as a result (`f is not None` to `True`) gives 3 results; s21 False
    # counted as an error (`f is True` to `f is not None`) gives 2 errors; s21 metadata keeps calls (tool_names
    # holds the call dicts) fails the equality.
    calls = [call("a", x=1), call("b"), call("a", x=1)]

    metadata = score_metadata(case(expected_tools=["a"]), calls, [False, True, None])

    assert metadata == {
        "tool_names": ["a", "b", "a"],
        "tool_results": 2,
        "tool_errors": 1,
        "redundant_tool_calls": 1,
        "tool_precision": 0.5,
        "tool_recall": 1.0,
    }


@pytest.mark.parametrize(
    "errors",
    [None, [True], [True, True, True]],
    ids=["not-recorded", "shorter-than-calls", "longer-than-calls"],
)
def test_score_metadata_treats_every_outcome_as_unknown_when_error_flags_do_not_line_up_with_calls(errors):
    # Witnesses: s21 short error list accepted (`==` to `<=`) fails shorter-than-calls; s21 long error list accepted
    # (`==` to `>=`) gives 3 errors for longer-than-calls.
    metadata = score_metadata(case(), [call("a"), call("b")], errors)

    assert (metadata["tool_results"], metadata["tool_errors"]) == (0, 0)
    assert metadata["tool_names"] == ["a", "b"]


def test_score_metadata_omits_selection_keys_when_the_case_declares_no_expected_tools():
    # Witness: s21 selection keys always written (`if expected is not None` dropped) fails on selection(names, None).
    metadata = score_metadata(case(forbidden_tools=["a"]), [call("a")], [False])

    assert set(metadata) == {"tool_names", "tool_results", "tool_errors", "redundant_tool_calls"}


def test_score_metadata_keeps_undefined_selection_as_none_when_no_tool_may_be_called_and_none_was():
    # Witness: s21 precision zero when no calls gives tool_precision 0.0.
    metadata = score_metadata(case(expected_tool_calls=[]), [], [])

    assert metadata == {
        "tool_names": [],
        "tool_results": 0,
        "tool_errors": 0,
        "redundant_tool_calls": 0,
        "tool_precision": None,
        "tool_recall": None,
    }


def test_score_metadata_serialisation_carries_no_argument_values_or_their_digest():
    # Witness: s21 metadata keeps calls (tool_names holds the call dicts) puts SECRET in the serialisation.
    calls = [call("lookup", query=SECRET), call("lookup", query=SECRET)]

    serialised = json.dumps(score_metadata(case(expected_tools=["lookup"]), calls, [False, False]))

    assert SECRET not in serialised
    assert "query" not in serialised
    assert re.search(r"[0-9a-f]{16,}", serialised) is None
    assert json.loads(serialised)["redundant_tool_calls"] == 1


# case_tool_use

@pytest.mark.parametrize(
    "scores",
    [
        [],
        [None, None],
        [Score(value="C", metadata=None)],
        [epoch(checks={}, tool_call_count=2)],
        [epoch(tool_names=None, tool_errors=1)],
    ],
    ids=["no-epochs", "unscored-epochs", "no-metadata", "older-log", "names-not-a-list"],
)
def test_case_tool_use_is_none_when_no_epoch_recorded_tool_names(scores):
    # Witness: s21 case without names returns empty (`if not epochs` dropped) gives a CaseToolUse with no epochs.
    assert case_tool_use(scores) is None


def test_case_tool_use_sums_counts_over_epochs_that_recorded_names_and_skips_the_rest():
    # Witnesses: s21 case epochs without names kept (isinstance check dropped) adds the older log's 5 errors; s21
    # case precision summed not averaged gives 1.5.
    scores = [
        epoch(
            tool_names=["a", "b", "a"],
            tool_results=3,
            tool_errors=1,
            redundant_tool_calls=1,
            tool_precision=0.5,
            tool_recall=1.0,
        ),
        None,
        epoch(checks={}, tool_call_count=4, tool_errors=5),
        epoch(tool_names=["a"], tool_results=1, tool_errors=0, redundant_tool_calls=0, tool_precision=1, tool_recall=1),
    ]

    result = case_tool_use(scores)

    assert result == CaseToolUse(
        calls_per_epoch=(3, 1),
        by_tool={"a": 3, "b": 1},
        results=4,
        errors=1,
        redundant=1,
        precision=0.75,
        recall=1.0,
    )


def test_case_tool_use_averages_selection_only_over_epochs_where_it_is_defined():
    # Witness: s21 case undefined precision as zero (None counted as 0.0) gives 0.5 rather than 1.0.
    scores = [
        epoch(tool_names=[], tool_precision=None, tool_recall=0.0),
        epoch(tool_names=["a"], tool_precision=1.0, tool_recall=1.0),
    ]

    result = case_tool_use(scores)

    assert (result.calls_per_epoch, result.precision, result.recall) == ((0, 1), 1.0, 0.5)


def test_case_tool_use_has_no_selection_when_the_case_declares_no_expected_tools():
    # Witness: s21 mean of nothing is zero (`else None` to `else 0.0`) gives (0.0, 0.0).
    result = case_tool_use([epoch(tool_names=["a"], tool_results=1, tool_errors=1, redundant_tool_calls=0)])

    assert (result.precision, result.recall) == (None, None)
    assert (result.calls_per_epoch, result.by_tool, result.errors) == ((1,), {"a": 1}, 1)



# run_tool_use

@pytest.mark.parametrize(
    "cases",
    [[], [None, None], [use(calls=(0, 0), by_tool={}), None]],
    ids=["no-cases", "nothing-recorded", "only-zero-call-epochs"],
)
def test_run_tool_use_is_none_when_no_case_called_a_tool(cases):
    # Witness: s21 run without calls kept (`if not any(...)` dropped) returns a RunToolUse.
    assert run_tool_use(cases) is None


def test_run_tool_use_sums_counts_and_macro_averages_selection_over_cases_that_define_it():
    # A case with four epochs at precision 1.0 and one with a single epoch at 0.0: macro gives 0.5, where pooling
    # the epochs would give 0.8. The case without expectations counts towards calls but not selection.
    # Witnesses: s21 run selection micro (weighted by epochs) gives 0.8; s21 run selection cases counts all gives 3;
    # s21 run None case kept raises AttributeError.
    cases = [
        use(calls=(1, 1, 1, 1), by_tool={"a": 4}, results=4, errors=1, redundant=0, precision=1.0, recall=1.0),
        None,
        use(calls=(2,), by_tool={"a": 1, "b": 1}, results=2, errors=0, redundant=1, precision=0.0, recall=0.5),
        use(calls=(3,), by_tool={"c": 3}, results=0, errors=0, redundant=2),
    ]

    run = run_tool_use(cases)

    assert run.calls_per_epoch == [1, 1, 1, 1, 2, 3]
    assert run.total == 9
    assert run.by_tool == Counter({"a": 5, "b": 1, "c": 3})
    assert (run.results, run.errors, run.redundant) == (6, 1, 3)
    assert (run.precision, run.recall, run.selection_cases) == (0.5, 0.75, 2)


def test_run_tool_use_counts_a_case_with_only_recall_defined_as_a_selection_case():
    # Witness: s21 selection case needs both ('or' to 'and') gives 0.
    run = run_tool_use([use(calls=(0, 1), precision=None, recall=0.0)])

    assert (run.precision, run.recall, run.selection_cases) == (None, 0.0, 1)



# tool_use_lines

@pytest.mark.parametrize(
    "cases",
    [[], [None], [use(calls=(0,), by_tool={})]],
    ids=["no-cases", "not-recorded", "zero-calls"],
)
def test_tool_use_section_is_omitted_when_no_case_called_a_tool(cases):
    # Witness: s21 lines omitted without calls dropped (`if run is None` removed) raises AttributeError.
    assert tool_use_lines(cases) == []


def test_tool_use_section_reports_counts_errors_redundancy_selection_and_tools_by_share():
    # Counts per case-epoch are 3, 1 and 4: 8 calls, mean 8/3, median 3, max 4. One error in four known results,
    # one redundant call in eight, and selection from the one case that declares expected tools.
    # Witnesses: s21 lines mean always integral (str(int(value))) gives "mean 2"; s21 lines error share of all calls
    # gives 12.5%; s21 lines redundant share of results gives 25.0%.
    cases = [
        use(calls=(3, 1), by_tool={"search": 3, "fetch": 1}, results=4, errors=1, redundant=1, precision=0.5, recall=1),
        use(calls=(4,), by_tool={"fetch": 4}),
    ]

    lines = tool_use_lines(cases)

    assert lines[:3] == ["", HEADER, ""]
    assert bullet(lines, "Calls") == "- Calls: 8 over 3 case-epoch(s); per case-epoch mean 2.7, median 3, max 4"
    assert bullet(lines, "Tool errors") == "- Tool errors: 1/4 calls with a recorded result (25.0%)"
    assert bullet(lines, "Redundant calls (same name and arguments as an earlier call in the epoch)") == (
        "- Redundant calls (same name and arguments as an earlier call in the epoch): 1/8 (12.5%)"
    )
    assert bullet(lines, "Tool selection vs expected tools") == (
        "- Tool selection vs expected tools: precision 50.0%, recall 100.0% (macro over 1 case(s))"
    )
    assert table_rows(lines) == ["| fetch | 5 | 62.5% |", "| search | 3 | 37.5% |"]


def test_tool_use_section_shows_an_integral_mean_and_median_without_decimals():
    # Witness: s21 lines number always one decimal gives "mean 2.0, median 2.0".
    lines = tool_use_lines([use(calls=(1, 3)), use(calls=(1, 3))])

    assert bullet(lines, "Calls") == "- Calls: 8 over 4 case-epoch(s); per case-epoch mean 2, median 2, max 3"


def test_tool_use_section_says_errors_are_not_recorded_when_no_outcome_is_known():
    # Witness: s21 lines unknown errors shown as zero (`if run.results` to `if True`) raises ZeroDivisionError.
    lines = tool_use_lines([use(calls=(2,), results=0, errors=0)])

    assert bullet(lines, "Tool errors") == "- Tool errors: not recorded by the adapter"



@pytest.mark.parametrize(
    ("precision", "recall", "line"),
    [
        (None, None, "n/a (no case declares expected tools)"),
        (None, 0.0, "precision n/a, recall 0.0% (macro over 1 case(s))"),
    ],
    ids=["no-case-declares", "precision-undefined"],
)
def test_tool_use_section_shows_undefined_selection_as_na(precision, recall, line):
    # Witness: s21 lines selection without cases shown (`if run.selection_cases` to `if True`) fails
    # no-case-declares with "precision n/a, recall n/a (macro over 0 case(s))".
    lines = tool_use_lines([use(calls=(1,), precision=precision, recall=recall)])

    assert bullet(lines, "Tool selection vs expected tools") == f"- Tool selection vs expected tools: {line}"


def test_tool_use_table_lists_the_top_tools_by_calls_then_name_and_folds_the_rest_into_one_row():
    # Witnesses: s21 lines ties unsorted (name dropped from the sort key) puts b before a; s21 lines other row
    # miscounted (`len(ranked) - 1`) gives "4 other tool(s)"; s21 lines top off by one shows three named rows.
    by_tool = {"d": 1, "c": 2, "b": 3, "a": 3, "e": 1}

    lines = tool_use_lines([use(calls=(10,), by_tool=by_tool)], top=2)

    assert table_rows(lines) == ["| a | 3 | 30.0% |", "| b | 3 | 30.0% |", "| 3 other tool(s) | 4 | 40.0% |"]


def test_tool_use_table_ranks_by_calls_before_name():
    # Witness: s21 lines sorted by name (count dropped from the sort key) puts alpha first.
    lines = tool_use_lines([use(calls=(5,), by_tool={"alpha": 1, "zulu": 4})])

    assert table_rows(lines) == ["| zulu | 4 | 80.0% |", "| alpha | 1 | 20.0% |"]


def test_tool_use_table_has_no_other_row_when_every_tool_fits():
    # Witness: s21 lines other row at exactly top (`>` to `>=`) adds "| 0 other tool(s) | 0 | 0.0% |".
    lines = tool_use_lines([use(calls=(3,), by_tool={"a": 2, "b": 1})], top=2)

    assert table_rows(lines) == ["| a | 2 | 66.7% |", "| b | 1 | 33.3% |"]


def test_tool_use_table_escapes_pipes_in_tool_names_so_each_row_keeps_three_cells():
    # Witness: s21 lines pipe unescaped gives "| a|b | 1 | 100.0% |".
    lines = tool_use_lines([use(calls=(1,), by_tool={"a|b": 1})])

    [row] = table_rows(lines)
    assert row == "| a\\|b | 1 | 100.0% |"
    assert len(row.replace("\\|", "").strip("|").split("|")) == 3

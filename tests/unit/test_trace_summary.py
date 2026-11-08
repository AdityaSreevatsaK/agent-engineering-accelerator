import json
from datetime import UTC, datetime, timedelta

import pytest

from agent_accelerator.trace_summary import summarise_traces

T0 = datetime(2026, 10, 12, 13, 47, 17, tzinfo=UTC)


def iso(seconds):
    return (T0 + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def span(trace_id, name, start, end, status="UNSET", **attributes):
    return {
        "name": name,
        "context": {"trace_id": trace_id},
        "start_time": iso(start),
        "end_time": iso(end),
        "attributes": attributes,
        "status": {"status_code": status},
    }


def root(trace_id, sample_id, start=0.0, end=10.0, epoch=None):
    attributes = {"eval.sample_id": sample_id}
    if epoch is not None:
        attributes["eval.epoch"] = epoch
    return span(trace_id, "eval_case", start, end, **attributes)


def strands_model(trace_id, start, end):
    return span(trace_id, "chat", start, end, **{"gen_ai.operation.name": "chat"})


def strands_tool(trace_id, tool, start, end, status="UNSET"):
    return span(
        trace_id,
        f"execute_tool {tool}",
        start,
        end,
        status,
        **{"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool},
    )


def langgraph_model(trace_id, start, end):
    return span(trace_id, "ChatModel", start, end, **{"openinference.span.kind": "LLM"})


def langgraph_tool(trace_id, tool, start, end, status="UNSET"):
    return span(trace_id, "tool", start, end, status, **{"openinference.span.kind": "TOOL", "tool.name": tool})


def write(tmp_path, *spans, lines=None):
    path = tmp_path / "traces.jsonl"
    rows = [json.dumps(s) for s in spans] if lines is None else lines
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def only(path):
    [summary] = summarise_traces(path)
    return summary


def test_strands_trace_counts_chat_spans_as_model_calls_and_execute_tool_spans_as_tool_calls(tmp_path):
    summary = only(
        write(
            tmp_path,
            root("t1", "a"),
            strands_model("t1", 1, 2),
            strands_tool("t1", "find_customer", 2, 3),
            strands_model("t1", 3, 4),
        )
    )

    assert summary.model_calls == 2
    assert summary.tool_calls == ["find_customer"]


def test_langgraph_trace_counts_llm_spans_as_model_calls_and_tool_spans_as_tool_calls(tmp_path):
    summary = only(
        write(
            tmp_path,
            root("t1", "a"),
            langgraph_model("t1", 1, 2),
            langgraph_tool("t1", "find_customer", 2, 3),
            langgraph_model("t1", 3, 4),
        )
    )

    assert summary.model_calls == 2
    assert summary.tool_calls == ["find_customer"]


def test_tool_name_falls_back_to_span_name_when_no_tool_name_attribute(tmp_path):
    summary = only(
        write(
            tmp_path,
            root("t1", "a"),
            span("t1", "get_order", 1, 2, **{"gen_ai.operation.name": "execute_tool"}),
            span("t1", "refund", 3, 4, **{"openinference.span.kind": "TOOL"}),
        )
    )

    assert summary.tool_calls == ["get_order", "refund"]


def test_equivalent_strands_and_langgraph_traces_give_equal_counts_and_tool_lists(tmp_path):
    strands = only(
        write(
            tmp_path,
            root("s", "a"),
            strands_model("s", 1, 2),
            strands_tool("s", "find_customer", 2, 3),
            strands_tool("s", "get_order", 3, 4, status="ERROR"),
            strands_model("s", 4, 5),
        )
    )
    langgraph = only(
        write(
            tmp_path,
            root("l", "a"),
            langgraph_model("l", 1, 2.5),
            langgraph_tool("l", "find_customer", 2.5, 3),
            langgraph_tool("l", "get_order", 3, 4.5, status="ERROR"),
            langgraph_model("l", 4.5, 5),
        )
    )

    assert strands.model_calls == langgraph.model_calls == 2
    assert strands.tool_calls == langgraph.tool_calls == ["find_customer", "get_order"]
    assert strands.tool_errors == langgraph.tool_errors == 1


def test_nested_non_model_non_tool_spans_count_as_neither(tmp_path):
    summary = only(
        write(
            tmp_path,
            root("t1", "a"),
            span("t1", "invoke_agent", 0.5, 9),
            span("t1", "execute_event_loop_cycle", 1, 8),
            span("t1", "LangGraph", 1, 8, **{"openinference.span.kind": "CHAIN"}),
            strands_model("t1", 2, 3),
            strands_tool("t1", "find_customer", 3, 4),
        )
    )

    assert summary.model_calls == 1
    assert summary.tool_calls == ["find_customer"]
    assert summary.model_time_s == pytest.approx(1.0)
    assert summary.tool_time_s == pytest.approx(1.0)


def test_tool_calls_follow_start_time_not_file_order(tmp_path):
    summary = only(
        write(
            tmp_path,
            strands_tool("t1", "get_order", 5, 6),
            root("t1", "a"),
            strands_tool("t1", "find_customer", 1, 2),
        )
    )

    assert summary.tool_calls == ["find_customer", "get_order"]


def test_tool_errors_count_only_error_status_on_tool_spans(tmp_path):
    summary = only(
        write(
            tmp_path,
            root("t1", "a"),
            span("t1", "execute_event_loop_cycle", 1, 2, status="ERROR"),
            strands_model("t1", 1, 2) | {"status": {"status_code": "ERROR"}},
            strands_tool("t1", "find_customer", 2, 3, status="ERROR"),
            strands_tool("t1", "get_order", 3, 4, status="OK"),
            strands_tool("t1", "refund", 4, 5, status="UNSET"),
        )
    )

    assert summary.tool_errors == 1


def test_model_and_tool_times_are_sums_of_durations_and_total_is_root_duration(tmp_path):
    summary = only(
        write(
            tmp_path,
            root("t1", "a", start=0, end=7.5),
            strands_model("t1", 1, 1.25),
            strands_model("t1", 2, 2.5),
            strands_tool("t1", "find_customer", 3, 3.5),
            strands_tool("t1", "get_order", 4, 6),
        )
    )

    assert summary.model_time_s == pytest.approx(0.75)
    assert summary.tool_time_s == pytest.approx(2.5)
    assert summary.total_time_s == pytest.approx(7.5)


def test_epoch_is_read_from_root_and_defaults_to_one(tmp_path):
    summaries = summarise_traces(
        write(
            tmp_path,
            root("t1", "a", epoch=3),
            root("t2", "b"),
        )
    )

    assert [(s.sample_id, s.epoch) for s in summaries] == [("a", 3), ("b", 1)]


def test_numeric_sample_id_is_returned_as_a_string(tmp_path):
    summary = only(write(tmp_path, root("t1", 7)))

    assert summary.sample_id == "7"


def test_traces_without_an_eval_case_root_are_ignored(tmp_path):
    summaries = summarise_traces(
        write(
            tmp_path,
            root("t1", "a"),
            span("orphan", "invoke_agent", 0, 1),
            strands_model("orphan", 0, 1),
            strands_tool("orphan", "find_customer", 0, 1),
        )
    )

    assert [s.sample_id for s in summaries] == ["a"]
    assert summaries[0].model_calls == 0
    assert summaries[0].tool_calls == []


def test_blank_lines_are_skipped(tmp_path):
    lines = ["", json.dumps(root("t1", "a")), "   ", json.dumps(strands_model("t1", 1, 2)), ""]

    summary = only(write(tmp_path, lines=lines))

    assert summary.model_calls == 1


def test_multiple_traces_are_sorted_by_sample_id_then_epoch(tmp_path):
    summaries = summarise_traces(
        write(
            tmp_path,
            root("t1", "b", epoch=2),
            root("t2", "a", epoch=2),
            root("t3", "b", epoch=1),
            root("t4", "a", epoch=1),
        )
    )

    assert [(s.sample_id, s.epoch) for s in summaries] == [("a", 1), ("a", 2), ("b", 1), ("b", 2)]

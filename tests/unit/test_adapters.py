import asyncio
import importlib
import sys
import textwrap

import pytest
from inspect_ai.model import ChatMessageTool, ModelName
from inspect_ai.solver import TaskState
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agent_accelerator.adapters import load_factory
from agent_accelerator.adapters.langgraph import _tool_errors as langgraph_tool_errors
from agent_accelerator.adapters.langgraph import _tool_messages as langgraph_tool_messages
from agent_accelerator.adapters.langgraph import langgraph_agent
from agent_accelerator.adapters.strands import _tool_errors as strands_tool_errors
from agent_accelerator.adapters.strands import _tool_messages as strands_tool_messages
from agent_accelerator.adapters.strands import strands_agent

DOUBLES = "aea_adapter_doubles"

# Agent factories for edge cases. Each factory builds a fresh agent around a scripted model double and
# counts its own calls in CALLS. A script entry is a tool call, a text reply, or an exception to raise.
DOUBLES_SOURCE = textwrap.dedent(
    '''
    import json
    from collections import Counter

    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.graph import END, START, MessagesState, StateGraph
    from strands import Agent, tool
    from strands.models.model import Model

    CALLS = Counter()
    NOT_CALLABLE = 42


    class CaseFailure(Exception):
        pass


    def plain_function():
        return "built"


    @tool
    def add_numbers(a: int, b: int) -> int:
        """Add two numbers.

        Args:
            a: Left operand.
            b: Right operand.
        """
        return a + b


    @tool
    def echo(text: str) -> str:
        """Echo the text back.

        Args:
            text: Text to echo.
        """
        return text


    @tool
    def fail(text: str) -> str:
        """Always fails.

        Args:
            text: Ignored.
        """
        raise CaseFailure("tool broke")


    class ScriptedModel(Model):
        def __init__(self, script, model_id="strands-double-7"):
            self._script = list(script)
            self._config = {"model_id": model_id}

        def update_config(self, **model_config):
            self._config.update(model_config)

        def get_config(self):
            return self._config

        def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
            raise NotImplementedError

        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
            turn = self._script.pop(0)
            if isinstance(turn, Exception):
                raise turn
            yield {"messageStart": {"role": "assistant"}}
            if turn[0] == "tool":
                _, name, arguments = turn[:3]
                use = {"toolUseId": f"call-{len(self._script)}", "name": name}
                yield {"contentBlockStart": {"start": {"toolUse": use}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(arguments)}}}}
                yield {"contentBlockStop": {}}
                yield {"messageStop": {"stopReason": "tool_use"}}
            else:
                yield {"contentBlockDelta": {"delta": {"text": turn[1]}}}
                yield {"contentBlockStop": {}}
                yield {"messageStop": {"stopReason": "end_turn"}}
            usage = turn[3] if turn[0] == "tool" else turn[2]
            if usage is not None:
                counts = dict(zip(("inputTokens", "outputTokens", "totalTokens"), usage))
                yield {"metadata": {"usage": counts, "metrics": {"latencyMs": 1}}}


    def _strands(name, script):
        CALLS[name] += 1
        return Agent(model=ScriptedModel(script), tools=[add_numbers, echo, fail], callback_handler=None)


    def strands_two_tools():
        script = [
            ("tool", "add_numbers", {"a": 1, "b": 2}, None),
            ("tool", "echo", {"text": "hi"}, None),
            ("text", " 3 and hi \\n", None),
        ]
        return _strands("strands_two_tools", script)


    def strands_no_tool():
        return _strands("strands_no_tool", [("text", "  plain reply  ", None)])


    def strands_usage():
        script = [("tool", "add_numbers", {"a": 1, "b": 2}, (3, 5, 8)), ("text", "3", (11, 13, 24))]
        return _strands("strands_usage", script)


    def strands_zero_usage():
        return _strands("strands_zero_usage", [("text", "3", (0, 0, 0))])


    def strands_raises():
        return _strands("strands_raises", [CaseFailure("boom")])


    def strands_tool_error():
        script = [
            ("tool", "add_numbers", {"a": 1, "b": 2}, None),
            ("tool", "fail", {"text": "x"}, None),
            ("text", "done", None),
        ]
        return _strands("strands_tool_error", script)


    def _usage(counts):
        if counts is None:
            return None
        return dict(zip(("input_tokens", "output_tokens", "total_tokens"), counts))


    def _ai(content="", tool_calls=(), model_name=None, usage=None, first_id=0):
        calls = [
            {"name": name, "args": args, "id": f"call-{first_id + i}", "type": "tool_call"}
            for i, (name, args) in enumerate(tool_calls)
        ]
        metadata = {"model_name": model_name} if model_name else {}
        return AIMessage(content=content, tool_calls=calls, response_metadata=metadata, usage_metadata=_usage(usage))


    def _graph(name, script):
        CALLS[name] += 1
        script = list(script)

        def model(state):
            turn = script.pop(0)
            if isinstance(turn, Exception):
                raise turn
            return {"messages": [turn]}

        def tools(state):
            last = state["messages"][-1]
            if any(c["name"] == "explode" for c in last.tool_calls):
                raise CaseFailure("tool node broke")
            return {
                "messages": [
                    ToolMessage(
                        content="ok", tool_call_id=c["id"], status="error" if c["name"] == "fail" else "success"
                    )
                    for c in last.tool_calls
                ]
            }

        def route(state):
            return "tools" if state["messages"][-1].tool_calls else END

        graph = StateGraph(MessagesState)
        graph.add_node("model", model)
        graph.add_node("tools", tools)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", route, ["tools", END])
        graph.add_edge("tools", "model")
        return graph.compile()


    def lg_two_tools():
        script = [
            _ai(tool_calls=[("add_numbers", {"a": 1, "b": 2})], model_name="lg-first", usage=(3, 5, 8)),
            _ai(tool_calls=[("echo", {"text": "hi"})], model_name="lg-second", usage=(11, 13, 24)),
            _ai(content=" 3 and hi \\n"),
        ]
        return _graph("lg_two_tools", script)


    def lg_no_tool():
        return _graph("lg_no_tool", [_ai(content="  plain reply  ")])


    def lg_raises_after_tool():
        script = [_ai(tool_calls=[("add_numbers", {"a": 1, "b": 2})]), CaseFailure("boom")]
        return _graph("lg_raises_after_tool", script)


    def lg_tool_error():
        script = [_ai(tool_calls=[("add_numbers", {"a": 1, "b": 2}), ("fail", {"text": "x"})]), _ai(content="done")]
        return _graph("lg_tool_error", script)


    def lg_tool_node_raises():
        script = [_ai(tool_calls=[("add_numbers", {"a": 1, "b": 2})]), _ai(tool_calls=[("explode", {})], first_id=1)]
        return _graph("lg_tool_node_raises", script)
    '''
)


@pytest.fixture(scope="module")
def doubles(tmp_path_factory):
    folder = tmp_path_factory.mktemp("doubles")
    (folder / f"{DOUBLES}.py").write_text(DOUBLES_SOURCE, encoding="utf-8")
    sys.path.insert(0, str(folder))
    try:
        yield importlib.import_module(DOUBLES)
    finally:
        sys.path.remove(str(folder))
        sys.modules.pop(DOUBLES, None)


@pytest.fixture(scope="module")
def span_exporter():
    # Adapters trace through the global provider, which can only be set once per process.
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.fixture
def spans(span_exporter):
    span_exporter.clear()
    return span_exporter


ADAPTERS = {"strands": strands_agent, "langgraph": langgraph_agent}


def solver_for(adapter, factory):
    return ADAPTERS[adapter](f"{DOUBLES}:{factory}")


def run_case(solver, text="What is 1 plus 2?", sample_id="case-1", epoch=1):
    state = TaskState(model=ModelName("none/none"), sample_id=sample_id, epoch=epoch, input=text, messages=[])
    return asyncio.run(solver(state, None))


# load_factory


def test_load_factory_returns_the_named_callable(doubles):
    assert load_factory(f"{DOUBLES}:plain_function") is doubles.plain_function


@pytest.mark.parametrize(
    "ref",
    [
        f"{DOUBLES}.plain_function",  # no colon
        ":plain_function",  # empty module
        f"{DOUBLES}:",  # empty attribute
    ],
)
def test_load_factory_malformed_reference_says_module_function_shape(doubles, ref):
    with pytest.raises(ValueError, match="must look like 'module:function'"):
        load_factory(ref)


def test_load_factory_unknown_attribute_says_has_no_attribute(doubles):
    with pytest.raises(ValueError, match="has no attribute 'no_such_function'"):
        load_factory(f"{DOUBLES}:no_such_function")


def test_load_factory_non_callable_attribute_says_not_callable(doubles):
    with pytest.raises(ValueError, match="is not callable"):
        load_factory(f"{DOUBLES}:NOT_CALLABLE")


def test_load_factory_unknown_module_raises_import_error():
    with pytest.raises(ImportError):
        load_factory("aea_no_such_module_xyz:build_agent")


# Shared adapter behaviour


TWO_TOOLS = [
    {"name": "add_numbers", "arguments": {"a": 1, "b": 2}},
    {"name": "echo", "arguments": {"text": "hi"}},
]


@pytest.mark.parametrize("adapter, factory", [("strands", "strands_two_tools"), ("langgraph", "lg_two_tools")])
def test_tool_calls_recorded_in_call_order_and_completion_stripped(doubles, spans, adapter, factory):
    state = run_case(solver_for(adapter, factory))

    assert state.metadata["agent_error"] is None
    assert state.metadata["tool_calls"] == TWO_TOOLS
    assert state.output.completion == "3 and hi"


@pytest.mark.parametrize("adapter, factory", [("strands", "strands_no_tool"), ("langgraph", "lg_no_tool")])
def test_case_without_tool_use_records_empty_tool_calls(doubles, spans, adapter, factory):
    state = run_case(solver_for(adapter, factory))

    assert state.metadata["tool_calls"] == []
    assert state.metadata["agent_error"] is None
    assert state.output.completion == "plain reply"


@pytest.mark.parametrize("adapter, factory", [("strands", "strands_two_tools"), ("langgraph", "lg_two_tools")])
def test_factory_is_called_once_per_case_attempt(doubles, spans, adapter, factory):
    solver = solver_for(adapter, factory)
    before = doubles.CALLS[factory]

    run_case(solver, sample_id="a", epoch=1)
    run_case(solver, sample_id="a", epoch=2)
    run_case(solver, sample_id="b", epoch=1)

    assert doubles.CALLS[factory] - before == 3


def expected_strands_error(doubles):
    # The adapter reports whatever the agent itself raises, so derive it from the agent directly.
    with pytest.raises(Exception) as raised:
        asyncio.run(doubles.strands_raises().invoke_async("What is 1 plus 2?"))
    return f"{type(raised.value).__name__}: {raised.value}"


def test_strands_agent_error_is_recorded_output_empty_and_next_case_runs(doubles, spans):
    expected = expected_strands_error(doubles)
    assert "boom" in expected

    failed = run_case(solver_for("strands", "strands_raises"))
    after = run_case(solver_for("strands", "strands_no_tool"))

    assert failed.metadata["agent_error"] == expected
    assert failed.output.completion == ""
    assert after.metadata["agent_error"] is None
    assert after.output.completion == "plain reply"


def test_langgraph_agent_error_keeps_earlier_tool_calls_and_next_case_runs(doubles, spans):
    failed = run_case(solver_for("langgraph", "lg_raises_after_tool"))
    after = run_case(solver_for("langgraph", "lg_no_tool"))

    assert failed.metadata["agent_error"] == "CaseFailure: boom"
    assert failed.output.completion == ""
    assert failed.metadata["tool_calls"] == [{"name": "add_numbers", "arguments": {"a": 1, "b": 2}}]
    assert after.metadata["agent_error"] is None
    assert after.output.completion == "plain reply"


# Tool errors


@pytest.mark.parametrize("adapter, factory", [("strands", "strands_tool_error"), ("langgraph", "lg_tool_error")])
def test_tool_errors_flag_each_call_whose_result_was_an_error_in_call_order(doubles, spans, adapter, factory):
    # Witnesses: s21 strands error inverted and s21 langgraph error inverted give [True, False]; s21 strands result
    # not matched by id and s21 langgraph result not matched by id give [None, None].
    state = run_case(solver_for(adapter, factory))

    assert [c["name"] for c in state.metadata["tool_calls"]] == ["add_numbers", "fail"]
    assert state.metadata["tool_errors"] == [False, True]


@pytest.mark.parametrize("adapter, factory", [("strands", "strands_no_tool"), ("langgraph", "lg_no_tool")])
def test_tool_errors_are_empty_when_no_tool_was_called(doubles, spans, adapter, factory):
    assert run_case(solver_for(adapter, factory)).metadata["tool_errors"] == []


def test_langgraph_tool_errors_are_none_for_a_call_whose_result_never_arrived(doubles, spans):
    # Witness: s21 langgraph missing result as success gives [False, False].
    state = run_case(solver_for("langgraph", "lg_tool_node_raises"))

    assert state.metadata["agent_error"] == "CaseFailure: tool node broke"
    assert [c["name"] for c in state.metadata["tool_calls"]] == ["add_numbers", "explode"]
    assert state.metadata["tool_errors"] == [False, None]


def test_strands_tool_errors_match_results_by_tool_use_id_and_are_none_without_a_result():
    # Strands turns a raising tool into an error result, so a missing result is only reachable from a transcript
    # cut short; this feeds one directly. Witnesses: s21 strands missing result as success gives [False, True];
    # s21 strands result not matched by id gives [None, None].
    messages = [
        {"role": "user", "content": [{"text": "go"}]},
        {
            "role": "assistant",
            "content": [
                {"toolUse": {"toolUseId": "u1", "name": "add_numbers", "input": {}}},
                {"toolUse": {"toolUseId": "u2", "name": "echo", "input": {}}},
            ],
        },
        {"role": "user", "content": [{"toolResult": {"toolUseId": "u2", "status": "error", "content": []}}]},
    ]

    assert strands_tool_errors(messages) == [None, True]


def _call(call_id, name="add_numbers"):
    return {"name": name, "args": {}, "id": call_id, "type": "tool_call"}


def _result(call_id, status):
    return ToolMessage(content=status, tool_call_id=call_id, status=status)


def _langgraph_tool_errors(messages):
    """Feeds _tool_errors the transcript and its AIMessages, as the adapter does."""
    return langgraph_tool_errors([m for m in messages if isinstance(m, AIMessage)], messages)


@pytest.mark.parametrize(
    ("first", "second", "errors"),
    [("error", "success", [True, False]), ("success", "error", [False, True])],
    ids=["error_then_success", "success_then_error"],
)
def test_langgraph_tool_errors_give_calls_reusing_an_id_that_ids_results_in_transcript_order(first, second, errors):
    # A graph may number its calls per turn, so a later turn reuses an earlier id; each call owns its own result.
    # Witness s45 lg tool errors last result wins: the per-id deque replaced by a dict, `pending[m.tool_call_id] =
    # m.status` and `errors.append(None if (s := pending.get(...)) is None else s == "error")` (langgraph.py:233-241),
    # gives both calls the second status.
    messages = [
        HumanMessage("go"),
        AIMessage(content="", tool_calls=[_call("call-1")]),
        _result("call-1", first),
        AIMessage(content="", tool_calls=[_call("call-1")]),
        _result("call-1", second),
        AIMessage(content="done"),
    ]

    assert _langgraph_tool_errors(messages) == errors


@pytest.mark.parametrize(("status", "error"), [("error", True), ("success", False)], ids=["error", "success"])
def test_langgraph_tool_errors_are_none_for_a_second_call_reusing_an_id_whose_only_result_went_to_the_first(
    status, error
):
    # Witness s45 lg tool errors last result wins (above) gives [error, error]. Witness s45 lg tool errors result not
    # consumed: `queue.popleft() -> queue[0]` (langgraph.py:241) also gives [error, error].
    messages = [
        HumanMessage("go"),
        AIMessage(content="", tool_calls=[_call("call-1")]),
        _result("call-1", status),
        AIMessage(content="", tool_calls=[_call("call-1")]),
    ]

    assert _langgraph_tool_errors(messages) == [error, None]


def test_langgraph_tool_errors_ignore_results_beyond_the_calls_that_share_their_id():
    # One call, two results for its id and one for an id nobody called: the call takes the first, the rest are dropped.
    # Witness s45 lg tool errors last result wins (above) gives [True]. Witness s45 lg tool errors queue reversed:
    # `.append(m.status)` -> `.appendleft(m.status)` (langgraph.py:236) gives [True].
    messages = [
        HumanMessage("go"),
        AIMessage(content="", tool_calls=[_call("call-1")]),
        _result("call-1", "success"),
        _result("call-1", "error"),
        _result("unused", "error"),
    ]

    assert _langgraph_tool_errors(messages) == [False]


def test_langgraph_tool_errors_follow_call_order_across_ai_messages_not_result_order():
    # Results arrive b, a, c; the errors list stays in call order a, b, c.
    # Witness s45 lg tool errors ai messages reversed: `for m in ai_messages:` -> `for m in reversed(ai_messages)`
    # (langgraph.py:238) gives [True, False, True].
    messages = [
        HumanMessage("go"),
        AIMessage(content="", tool_calls=[_call("a"), _call("b", "fail")]),
        _result("b", "error"),
        _result("a", "success"),
        AIMessage(content="", tool_calls=[_call("c", "fail")]),
        _result("c", "error"),
    ]

    assert _langgraph_tool_errors(messages) == [False, True, True]


def test_langgraph_tool_errors_match_a_call_without_an_id_to_a_result_with_an_empty_id():
    # Witness s45 lg tool errors missing id not empty: `call.get("id") or ""` -> `call.get("id")` (langgraph.py:240)
    # gives [None].
    messages = [HumanMessage("go"), AIMessage(content="", tool_calls=[_call(None)]), _result("", "error")]

    assert _langgraph_tool_errors(messages) == [True]


def test_langgraph_tool_errors_have_one_entry_per_tool_call_even_when_no_result_arrived():
    # Witness s45 lg tool errors only answered calls: `errors.append(queue.popleft() == "error" if queue else None)`
    # -> `errors.extend([queue.popleft() == "error"] if queue else [])` (langgraph.py:241) gives [True].
    messages = [
        HumanMessage("go"),
        AIMessage(content="", tool_calls=[_call("a"), _call("b")]),
        _result("b", "error"),
        AIMessage(content="", tool_calls=[_call("c")]),
    ]

    assert _langgraph_tool_errors(messages) == [None, True, None]


def _strands_uses(*use_ids):
    return {
        "role": "assistant",
        "content": [{"toolUse": {"toolUseId": u, "name": "add_numbers", "input": {}}} for u in use_ids],
    }


def _strands_results(*results):
    """One user message holding a toolResult per (toolUseId, status); a status of None leaves the key off."""
    blocks = [
        {"toolResult": {"toolUseId": u, "content": [], **({"status": s} if s is not None else {})}} for u, s in results
    ]
    return {"role": "user", "content": blocks}


@pytest.mark.parametrize(
    ("first", "second", "errors"),
    [("error", "success", [True, False]), ("success", "error", [False, True])],
    ids=["error_then_success", "success_then_error"],
)
def test_strands_tool_errors_give_calls_reusing_an_id_that_ids_results_in_transcript_order(first, second, errors):
    # Witness s46 strands tool errors last result wins: the per-id deque replaced by a dict, `pending[id] = status` and
    # `status = pending.get(id)` (strands.py:87-97), gives both calls the second status. Witness s46 strands tool
    # errors queue reversed: `.append(...)` -> `.appendleft(...)` (strands.py:91) swaps the two.
    messages = [
        {"role": "user", "content": [{"text": "go"}]},
        _strands_uses("tooluse_1"),
        _strands_results(("tooluse_1", first)),
        _strands_uses("tooluse_1"),
        _strands_results(("tooluse_1", second)),
    ]

    assert strands_tool_errors(messages) == errors


@pytest.mark.parametrize(("status", "error"), [("error", True), ("success", False)], ids=["error", "success"])
def test_strands_tool_errors_are_none_for_a_second_call_reusing_an_id_whose_only_result_went_to_the_first(
    status, error
):
    # Witness s46 strands tool errors last result wins (above) gives [error, error]. Witness s46 strands tool errors
    # result not consumed: `queue.popleft()` -> `queue[0]` (strands.py:97) also gives [error, error].
    messages = [_strands_uses("tooluse_1"), _strands_results(("tooluse_1", status)), _strands_uses("tooluse_1")]

    assert strands_tool_errors(messages) == [error, None]


def test_strands_tool_errors_ignore_results_beyond_the_calls_that_share_their_id():
    # One call, two results for its id and one for an id nobody called: the call takes the first, the rest are dropped.
    # Witness s46 strands tool errors last result wins (above) gives [True]. Witness s46 strands tool errors queue
    # reversed (above) gives [True].
    messages = [
        _strands_uses("tooluse_1"),
        _strands_results(("tooluse_1", "success"), ("tooluse_1", "error"), ("tooluse_9", "error")),
    ]

    assert strands_tool_errors(messages) == [False]


def test_strands_tool_errors_match_results_arriving_out_of_call_order_by_id_not_position():
    # Results arrive b, a, c; the errors list stays in call order a, b, c.
    # Witness s46 strands tool errors matched by position: every result queued under one key and every use reading
    # it (strands.py:91-96) gives [True, False, True].
    messages = [
        _strands_uses("a", "b"),
        _strands_results(("b", "error"), ("a", "success")),
        _strands_uses("c"),
        _strands_results(("c", "error")),
    ]

    assert strands_tool_errors(messages) == [False, True, True]


def test_strands_tool_errors_are_none_for_a_use_without_a_tool_use_id_and_keep_one_entry_per_use():
    # Witness s46 strands tool errors use id required: `block["toolUse"].get("toolUseId")` ->
    # `block["toolUse"]["toolUseId"]` (strands.py:96) raises KeyError. Witness s46 strands tool errors idless use
    # skipped: `if "toolUse" in block:` -> `if "toolUse" in block and block["toolUse"].get("toolUseId"):`
    # (strands.py:95) gives [True], one entry short of _tool_calls.
    messages = [
        {"role": "assistant", "content": [{"toolUse": {"name": "add_numbers", "input": {}}}]},
        _strands_uses("tooluse_1"),
        _strands_results(("tooluse_1", "error")),
    ]

    assert strands_tool_errors(messages) == [None, True]


def test_strands_tool_errors_let_a_result_without_a_status_consume_its_calls_slot_and_give_none():
    # The first call's result has no status, so its outcome is unknown; the second call still owns the error.
    # Witness s46 strands tool errors statusless result skipped: queue a result only when it has a status
    # (strands.py:90) gives [True, None], the error moved onto the wrong call.
    messages = [
        _strands_uses("tooluse_1"),
        _strands_results(("tooluse_1", None)),
        _strands_uses("tooluse_1"),
        _strands_results(("tooluse_1", "error")),
    ]

    assert strands_tool_errors(messages) == [None, True]


def test_strands_tool_errors_raise_key_error_for_a_tool_result_without_a_tool_use_id():
    # Characterisation, unchanged by 4c9d80e: a result with no id is a malformed transcript and is not guessed at.
    # Witness s46 strands tool errors idless result tolerated: `block["toolResult"]["toolUseId"]` ->
    # `block["toolResult"].get("toolUseId")` (strands.py:91) returns [None].
    messages = [_strands_uses("tooluse_1"), {"role": "user", "content": [{"toolResult": {"status": "error"}}]}]

    with pytest.raises(KeyError, match="toolUseId"):
        strands_tool_errors(messages)


# Usage and model id


@pytest.mark.parametrize("factory", ["strands_no_tool", "strands_zero_usage"])
def test_strands_usage_is_none_when_unreported_or_all_zero(doubles, spans, factory):
    assert run_case(solver_for("strands", factory)).metadata["usage"] is None


def test_strands_usage_sums_reported_counts(doubles, spans):
    usage = run_case(solver_for("strands", "strands_usage")).metadata["usage"]

    assert usage == {"inputTokens": 14, "outputTokens": 18, "totalTokens": 32}


def test_strands_model_id_comes_from_model_config(doubles, spans):
    assert run_case(solver_for("strands", "strands_no_tool")).metadata["model_id"] == "strands-double-7"


def test_langgraph_usage_sums_counts_across_ai_messages(doubles, spans):
    usage = run_case(solver_for("langgraph", "lg_two_tools")).metadata["usage"]

    assert usage == {"inputTokens": 14, "outputTokens": 18, "totalTokens": 32}


def test_langgraph_usage_and_model_id_none_when_unreported(doubles, spans):
    state = run_case(solver_for("langgraph", "lg_no_tool"))

    assert state.metadata["usage"] is None
    assert state.metadata["model_id"] is None


def test_langgraph_model_id_comes_from_first_ai_message(doubles, spans):
    assert run_case(solver_for("langgraph", "lg_two_tools")).metadata["model_id"] == "lg-first"


# eval_case span


def eval_case_spans(exporter):
    return [s for s in exporter.get_finished_spans() if s.name == "eval_case"]


@pytest.mark.parametrize("adapter, factory", [("strands", "strands_no_tool"), ("langgraph", "lg_no_tool")])
def test_each_case_runs_in_an_eval_case_span_with_sample_id_and_epoch(doubles, spans, adapter, factory):
    run_case(solver_for(adapter, factory), sample_id=7, epoch=2)

    [span] = eval_case_spans(spans)
    sample_id, epoch = span.attributes["eval.sample_id"], span.attributes["eval.epoch"]
    assert sample_id == "7" and isinstance(sample_id, str)
    assert epoch == 2 and isinstance(epoch, int) and not isinstance(epoch, bool)
    assert [e.name for e in span.events if e.name == "exception"] == []


@pytest.mark.parametrize("adapter, factory", [("strands", "strands_raises"), ("langgraph", "lg_raises_after_tool")])
def test_agent_error_records_exception_event_on_eval_case_span(doubles, spans, adapter, factory):
    run_case(solver_for(adapter, factory))

    [span] = eval_case_spans(spans)
    assert "exception" in [e.name for e in span.events]


# Tool messages for the judge


def tool_messages(state):
    return [m for m in state.messages if isinstance(m, ChatMessageTool)]


def as_tuples(messages):
    return [(m.text, m.tool_call_id, m.function, m.error.message if m.error else None) for m in messages]


def test_langgraph_tool_messages_one_per_tool_message_in_order_with_text_id_name_and_error():
    # List content is read as its text blocks joined, as LangChain's .text gives it.
    # Witnesses: "s36 langgraph tool messages reversed"; "s36 langgraph content repr" (str(m.content)) fails the list
    # content; "s36 langgraph function dropped" (function=None); "s36 langgraph tool_call_id dropped"; "s36
    # langgraph error inverted" (!= "error").
    messages = [
        HumanMessage("go"),
        AIMessage(content="", tool_calls=[{"name": "get_claim", "args": {}, "id": "c1", "type": "tool_call"}]),
        ToolMessage(
            content=[{"type": "text", "text": "claim "}, {"type": "text", "text": "7"}],
            tool_call_id="c1",
            name="get_claim",
        ),
        ToolMessage(content="no such policy", tool_call_id="c2", name="get_policy", status="error"),
        AIMessage(content="done"),
    ]

    assert as_tuples(langgraph_tool_messages(messages)) == [
        ("claim 7", "c1", "get_claim", None),
        ("no such policy", "c2", "get_policy", "no such policy"),
    ]


def test_langgraph_tool_messages_are_kept_after_a_failed_stream(doubles, spans):
    # The graph raises after its first tool result; the partial snapshot still holds it.
    # Witness: "s36 langgraph tool messages only on success" (extend only when error is None) records none.
    state = run_case(solver_for("langgraph", "lg_raises_after_tool"))

    assert state.metadata["agent_error"] == "CaseFailure: boom"
    assert as_tuples(tool_messages(state)) == [("ok", "call-0", None, None)]
    assert state.metadata["tool_calls"] == [{"name": "add_numbers", "arguments": {"a": 1, "b": 2}}]


def test_strands_tool_messages_one_per_tool_result_with_text_and_json_and_the_matching_function():
    # Results arrive in a different order from the uses, so a name taken by position would be wrong; u9 has no use.
    # Witnesses: "s36 strands tool messages reversed"; "s36 strands function dropped" (function=None); "s36 strands
    # unmatched function named" (names.get(id, "unknown")); "s36 strands tool_call_id dropped"; "s36 strands json
    # repr" (str(b["json"])); "s36 strands parts space joined"; "s36 strands image not skipped" (no text/json filter)
    # raises KeyError; "s36 strands error inverted" (!= "error").
    messages = [
        {"role": "user", "content": [{"text": "go"}]},
        {
            "role": "assistant",
            "content": [
                {"text": "calling"},
                {"toolUse": {"toolUseId": "u1", "name": "get_claim", "input": {}}},
                {"toolUse": {"toolUseId": "u2", "name": "get_policy", "input": {}}},
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "u2",
                        "status": "error",
                        "content": [
                            {"text": "no such policy"},
                            {"image": {"format": "png", "source": {"bytes": b"x"}}},
                        ],
                    }
                },
                {
                    "toolResult": {
                        "toolUseId": "u1",
                        "status": "success",
                        "content": [{"text": "claim 7"}, {"json": {"amount": 120}}, {"document": {"name": "d"}}],
                    }
                },
            ],
        },
        {"role": "user", "content": [{"toolResult": {"toolUseId": "u9", "status": "success", "content": []}}]},
    ]

    assert as_tuples(strands_tool_messages(messages)) == [
        ("no such policy", "u2", "get_policy", "no such policy"),
        ('claim 7\n{"amount": 120}', "u1", "get_claim", None),
        ("", "u9", None, None),
    ]


def test_strands_tool_messages_are_recorded_on_the_state_for_each_result(doubles, spans):
    # Witness: "s36 strands tool messages not recorded" (extend with []) records none.
    state = run_case(solver_for("strands", "strands_tool_error"))

    recorded = tool_messages(state)
    assert [(m.function, m.error is not None) for m in recorded] == [("add_numbers", False), ("fail", True)]
    assert recorded[0].text == "3"
    assert state.metadata["tool_errors"] == [False, True]

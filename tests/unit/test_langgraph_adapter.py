import asyncio
import importlib
import json
import math
import sys
import textwrap
import uuid

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.model import ChatMessageTool, ModelName
from inspect_ai.scorer import CORRECT
from inspect_ai.solver import TaskState

from langchain_core.messages import AIMessage

from agent_accelerator.adapters.langgraph import _dedupe, _json_safe, langgraph_agent
from agent_accelerator.cli import main
from agent_accelerator.dataset import DATASET_FORMAT_VERSION, Case, load_dataset
from agent_accelerator.run import build_task, run_task
from agent_accelerator.scorers import CASE_CHECKS, run_checks

DOUBLES = "aea_lg_contract_doubles"
QUESTION = "What is 1 plus 2?"


class Opaque:
    """A value JSON cannot hold, with a fixed repr."""

    def __repr__(self):
        return "Opaque()"


OPAQUE = Opaque()

# Graph factories and maps for the adapter contract. Each factory builds a fresh graph; RECEIVED records what a
# recording graph's astream was called with, and SHARED_SAVER is one checkpointer shared by every graph built from
# counts_messages, so a reused thread id would show up as remembered messages.
DOUBLES_SOURCE = textwrap.dedent(
    """
    import operator
    from typing import Annotated, Any, TypedDict

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.func import entrypoint
    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.graph.message import add_messages
    from langgraph.types import Interrupt, Overwrite, interrupt
    from pydantic import BaseModel

    RECEIVED = []
    SHARED_SAVER = InMemorySaver()
    SECRET = "approve the 5000 USD claim of employee 7?"


    class Boom(Exception):
        pass


    class Decision(BaseModel):
        decision: str
        amount: float


    def usage(i, o):
        return {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}


    def ai(content="", calls=(), id=None, usage=None):
        tool_calls = [{"name": n, "args": a, "id": c, "type": "tool_call"} for n, a, c in calls]
        return AIMessage(content=content, tool_calls=tool_calls, id=id, usage_metadata=usage)


    def lookup(**kwargs):
        return ai(calls=[("lookup", {"x": 1}, "t1")], **kwargs)


    def found(**kwargs):
        return ToolMessage("found", tool_call_id="t1", **kwargs)


    def _done_with_usage(state):
        return {"messages": [ai("done", usage=usage(10, 20))]}


    def linear(state, *nodes):
        graph = StateGraph(state)
        names = [f"n{i}" for i in range(len(nodes))]
        for name, node in zip(names, nodes):
            graph.add_node(name, node)
        for a, b in zip([START, *names], [*names, END]):
            graph.add_edge(a, b)
        return graph


    def reply(text):
        return lambda state: {"messages": [ai(text)]}


    # Factory types

    def uncompiled():
        return linear(MessagesState, reply("from the builder"))


    def not_a_graph():
        return "a graph"


    def plain_reply():
        return linear(MessagesState, reply("plain reply")).compile()


    # Input

    def echo():
        def node(state):
            return {"messages": [ai("|".join(f"{type(m).__name__}:{m.text}" for m in state["messages"]))]}

        return linear(MessagesState, node).compile()


    class Question(TypedDict):
        question: str
        answer: str


    def custom_state():
        return linear(Question, lambda state: {"answer": "answer to " + state["question"]}).compile()


    class Trail(TypedDict):
        question: str
        trail: Annotated[list, operator.add]


    def trail_only():
        return linear(Trail, lambda state: {"trail": [ai("trail answer")]}).compile()


    def to_question(question):
        return {"question": question}


    def to_messages(question):
        return {"messages": [HumanMessage("mapped " + question)]}


    def to_text(question):
        return question


    def answer_of(state):
        return " " + state["answer"] + " \\n"


    def int_answer(state):
        return 42


    def last_message_text(state):
        return state["messages"][-1].text


    def shouted(state):
        return state.upper()


    # Answer

    class Structured(TypedDict):
        messages: Annotated[list, add_messages]
        structured_response: Any


    def _structured(value):
        return linear(Structured, lambda state: {"messages": [ai("message text")], "structured_response": value})


    def structured_str():
        return _structured("  approved  ").compile()


    def structured_dict():
        return _structured({"decision": "approve", "amount": 1.5}).compile()


    def structured_model():
        return _structured(Decision(decision="approve", amount=1.5)).compile()


    def structured_none():
        return _structured(None).compile()


    def trailing_human():
        return linear(MessagesState, lambda state: {"messages": [ai("the answer"), HumanMessage("later")]}).compile()


    def adds_nothing():
        return linear(MessagesState, lambda state: {}).compile()


    def content_blocks():
        blocks = [{"type": "text", "text": " Par"}, {"type": "text", "text": "is "}]
        return linear(MessagesState, lambda state: {"messages": [AIMessage(content=blocks)]}).compile()


    def str_entrypoint():
        @entrypoint()
        def run(inputs):
            return "plain words"

        return run


    # Interrupt

    def _ask(state):
        interrupt(SECRET)
        return {"messages": [ai("approved after asking")]}


    def interrupts():
        return linear(MessagesState, _ask).compile(checkpointer=InMemorySaver())


    def interrupts_without_checkpointer():
        return linear(MessagesState, _ask).compile()


    def interrupts_in_subgraph():
        return linear(MessagesState, linear(MessagesState, _ask).compile()).compile(checkpointer=InMemorySaver())


    class Opaque:
        def __repr__(self):
            return "opaque(7)"


    def two_interrupts_in_one_state():
        # A final root state holding two interrupts in a fixed order, one with a payload JSON cannot hold as it is.
        graph = linear(MessagesState, reply("never read")).compile()
        pending = (
            Interrupt({"step": "first", "who": ("employee", 7), "what": Opaque()}, id="i-1"),
            Interrupt("second", id="i-2"),
        )

        async def astream(input, config=None, **kwargs):
            yield (), "values", {"messages": [], "__interrupt__": pending}

        graph.astream = astream
        return graph


    def repeated_interrupt_across_root_chunks():
        # The same pending interrupt (same id) in two root "values" chunks, the second listing it after a new one.
        graph = linear(MessagesState, reply("never read")).compile()
        first, second = Interrupt("first", id="i-1"), Interrupt("second", id="i-2")

        async def astream(input, config=None, **kwargs):
            yield (), "values", {"messages": [], "__interrupt__": (first,)}
            yield (), "values", {"messages": [], "__interrupt__": (second, first)}

        graph.astream = astream
        return graph


    def _ask_a(state):
        interrupt("from a")
        return {}


    def _ask_b(state):
        interrupt("from b")
        return {}


    def parallel_interrupts():
        # Two parallel nodes, so one step raises two interrupts.
        graph = StateGraph(MessagesState)
        graph.add_node("a", _ask_a)
        graph.add_node("b", _ask_b)
        graph.add_edge(START, "a")
        graph.add_edge(START, "b")
        return graph.compile()


    def raises():
        def node(state):
            raise Boom("graph broke")

        return linear(MessagesState, node).compile()


    # Trajectory

    def _inner_lookup(state):
        return {"messages": [lookup(), found(name="lookup")]}


    def invoked_subgraph():
        inner = linear(MessagesState, _inner_lookup).compile()

        def call(state):
            inner.invoke({"messages": []})
            finish = ai(calls=[("finish", {}, "t2")])
            return {"messages": [finish, ToolMessage("finished", tool_call_id="t2", name="finish")]}

        return linear(MessagesState, call, reply("done")).compile()


    def invoked_subgraph_then_raises():
        inner = linear(MessagesState, _inner_lookup).compile()

        def call(state):
            inner.invoke({"messages": []})
            raise Boom("after the subgraph")

        return linear(MessagesState, call).compile()


    def subgraph_node():
        return linear(MessagesState, linear(MessagesState, _inner_lookup).compile(), reply("done")).compile()


    class Plain(TypedDict):
        messages: Annotated[list, operator.add]


    def _idless_lookup():
        # operator.add assigns no ids, so the subgraph's messages stay id-less.
        def node(state):
            return {"messages": [lookup(usage=usage(1, 2)), found()]}

        return linear(Plain, node).compile()


    def _idd_lookup(state):
        return {
            "messages": [
                lookup(id="ai-1", usage=usage(1, 2)),
                found(id="tm-1"),
            ]
        }


    def idless_then_idd():
        inner = _idless_lookup()

        def call(state):
            inner.invoke({"messages": []})
            return _idd_lookup(state)

        return linear(MessagesState, call, _done_with_usage).compile()


    def idd_then_idless():
        inner = _idless_lookup()

        def call(state):
            inner.invoke({"messages": []})
            return {}

        return linear(MessagesState, _idd_lookup, call, _done_with_usage).compile()


    def reused_call_ids():
        def node(state):
            return {
                "messages": [
                    ai(calls=[("lookup", {"x": 1}, "call-0")], id="ai-1"),
                    ToolMessage("one", tool_call_id="call-0", id="tm-1"),
                    ai(calls=[("lookup", {"x": 2}, "call-0")], id="ai-2"),
                    ToolMessage("two", tool_call_id="call-0", id="tm-2"),
                    ai("done", id="ai-3"),
                ]
            }

        return linear(MessagesState, node).compile()


    class Audited(TypedDict):
        messages: Annotated[list, add_messages]
        trail: Annotated[list, operator.add]


    def every_update_value():
        return linear(
            Audited,
            lambda state: {"trail": [ai(calls=[("audit", {}, "a1")]), ToolMessage("logged", tool_call_id="a1")]},
            lambda state: {"messages": Overwrite([lookup(), found()])},
            lambda state: None,
            lambda state: {"messages": ai(calls=[("single", {}, "s1")])},
            reply("done"),
        ).compile()


    def idless_answers():
        def node(state):
            return {"trail": [ai("draft one", usage=usage(1, 2)), ai("draft two", usage=usage(3, 4))]}

        return linear(Audited, node, reply("done")).compile()


    def plain_subgraph_node():
        # operator.add in both graphs: the subgraph node's id-less reply and the parent's re-emission are one object.
        inner = linear(Plain, lambda state: {"messages": [ai("done", usage=usage(1, 2))]}).compile()
        return linear(Plain, inner).compile()


    def equal_idless_answers():
        def node(state):
            return {"messages": [ai("same", usage=usage(1, 2)), ai("same", usage=usage(1, 2))]}

        return linear(Plain, node).compile()


    # Config

    def recording():
        graph = linear(MessagesState, reply("recorded")).compile()
        original = graph.astream

        def astream(input, config=None, **kwargs):
            RECEIVED.append((input, config, kwargs))
            return original(input, config, **kwargs)

        graph.astream = astream
        return graph


    def counts_messages():
        def node(state):
            return {"messages": [ai(str(len(state["messages"])))]}

        return linear(MessagesState, node).compile(checkpointer=SHARED_SAVER)


    def with_checkpointer():
        return linear(MessagesState, reply("saved")).compile(checkpointer=InMemorySaver())
    """
)


@pytest.fixture(scope="module")
def doubles(tmp_path_factory):
    folder = tmp_path_factory.mktemp("lg_doubles")
    (folder / f"{DOUBLES}.py").write_text(DOUBLES_SOURCE, encoding="utf-8")
    sys.path.insert(0, str(folder))
    try:
        yield importlib.import_module(DOUBLES)
    finally:
        sys.path.remove(str(folder))
        sys.modules.pop(DOUBLES, None)


def ref(name):
    return f"{DOUBLES}:{name}" if name else None


def run(factory, input_map=None, output_map=None, text=QUESTION, case=None):
    """Runs one case through the adapter. case is the raw case metadata; None leaves the metadata without a case."""
    solver = langgraph_agent(ref(factory), input_map=ref(input_map), output_map=ref(output_map))
    metadata = {"case": case} if case is not None else {}
    state = TaskState(
        model=ModelName("none/none"), sample_id="case-1", epoch=1, input=text, messages=[], metadata=metadata
    )
    return asyncio.run(solver(state, None))


def calls(state):
    return state.metadata["tool_calls"]


def tool_results(state):
    return [(m.tool_call_id, m.text) for m in state.messages if isinstance(m, ChatMessageTool)]


# Factory types


def test_an_uncompiled_state_graph_is_compiled_and_run(doubles):
    # Witness: "s38 lg builder not compiled" (return built) fails it as not a local graph.
    state = run("uncompiled")

    assert state.metadata["agent_error"] is None
    assert state.output.completion == "from the builder"


def test_a_factory_returning_no_graph_fails_the_case_and_the_next_case_runs(doubles):
    # Witnesses: "s38 lg any object accepted" (isinstance Pregel -> True) fails with an AttributeError instead; "s38 lg
    # non-graph message" changes the message.
    failed = run("not_a_graph")
    after = run("plain_reply")

    assert failed.metadata["agent_error"] == (
        "UnsupportedGraphError: not a local LangGraph graph; deployed agents are not supported"
    )
    assert failed.output.completion == ""
    assert calls(failed) == []
    assert after.metadata["agent_error"] is None
    assert after.output.completion == "plain reply"


# Input


def test_without_an_input_map_the_question_is_sent_as_one_human_message(doubles):
    # Witness: "s38 lg default input not the question" sends a different text.
    assert run("echo").output.completion == f"HumanMessage:{QUESTION}"


def test_an_input_map_replaces_the_default_input_even_when_the_graph_has_messages(doubles):
    # Witness: "s38 lg input map ignored" (if False) sends the default input.
    assert run("echo", input_map="to_messages").output.completion == f"HumanMessage:mapped {QUESTION}"


@pytest.mark.parametrize("factory", ["custom_state", "trail_only"], ids=["no-message-list", "message-list-not-named"])
def test_a_graph_without_a_messages_channel_fails_naming_input_map(doubles, factory):
    # trail_only keeps its messages under "trail": only a channel named "messages" takes the default input.
    # Witness: "s38 lg messages channel check dropped" (if False) sends the messages input, and the run then fails with
    # NoAnswerError instead.
    state = run(factory)

    assert state.metadata["agent_error"] == (
        "MissingInputMapError: graph has no 'messages' channel; pass --input-map module:function to build its input"
    )
    assert state.output.completion == ""


def test_custom_state_runs_with_an_input_map_and_an_output_map_whose_answer_is_stripped(doubles):
    # Witnesses: "s38 lg output map ignored" (if False) gives NoAnswerError; "s38 lg output map not stripped".
    state = run("custom_state", input_map="to_question", output_map="answer_of")

    assert state.metadata["agent_error"] is None
    assert state.output.completion == f"answer to {QUESTION}"


def test_an_input_map_that_returns_no_dict_fails_the_case_naming_the_type(doubles):
    # Witness: "s38 lg input map type unchecked" passes the str on, and LangGraph fails with its own error.
    state = run("custom_state", input_map="to_text", output_map="answer_of")

    assert state.metadata["agent_error"] == "TypeError: --input-map must return a dict, got str"


@pytest.mark.parametrize(
    ("input_map", "output_map", "error"),
    [("aea_no_such_module_xyz:to_input", None, ImportError), (None, "no_colon", ValueError)],
    ids=["input-map-module-missing", "output-map-malformed"],
)
def test_a_map_reference_that_cannot_be_loaded_fails_when_the_solver_is_built(doubles, input_map, output_map, error):
    # Witnesses: "s38 lg input map not loaded" (to_input = None) and "s38 lg output map not loaded" (to_answer = None)
    # build the solver without loading the map.
    with pytest.raises(error):
        langgraph_agent(ref("echo"), input_map=input_map, output_map=output_map)


# Answer


def test_an_output_map_wins_over_structured_response(doubles):
    # Witness: "s38 lg output map ignored" (as above) answers with the structured_response JSON.
    assert run("structured_dict", output_map="last_message_text").output.completion == "message text"


def test_an_output_map_that_returns_no_str_fails_the_case_naming_the_type(doubles):
    # Witness: "s38 lg output map type unchecked" calls .strip() on the int, an AttributeError.
    state = run("custom_state", input_map="to_question", output_map="int_answer")

    assert state.metadata["agent_error"] == "TypeError: --output-map must return a str, got int"
    assert state.output.completion == ""


@pytest.mark.parametrize(
    ("factory", "answer"),
    [
        ("structured_str", "approved"),
        ("structured_dict", {"decision": "approve", "amount": 1.5}),
        ("structured_model", {"decision": "approve", "amount": 1.5}),
    ],
    ids=["str", "dict", "pydantic"],
)
def test_structured_response_is_the_answer_over_the_last_ai_message(doubles, factory, answer):
    # A str is the answer as it is (stripped), anything else is its JSON.
    # Witnesses: "s38 lg structured_response ignored" (structured = None) answers "message text"; "s38 lg structured str
    # json quoted" (if False) gives '"approved"'; "s38 lg structured pydantic not dumped" (if False) raises TypeError;
    # "s38 lg structured dict as repr" (str(value)) is not JSON.
    completion = run(factory).output.completion

    assert (completion if isinstance(answer, str) else json.loads(completion)) == answer


def test_a_structured_response_of_none_falls_through_to_the_last_ai_message(doubles):
    # Witness: "s38 lg structured None used" (is not None -> True) answers "null".
    assert run("structured_none").output.completion == "message text"


def test_the_answer_is_the_last_ai_message_never_a_later_human_message(doubles):
    # Witness: "s38 lg last message of any type" (isinstance AIMessage -> True) answers "later".
    assert run("trailing_human").output.completion == "the answer"


def test_a_graph_that_adds_no_ai_message_fails_with_no_answer_produced(doubles):
    # Witnesses: "s38 lg last message of any type" (as above) answers with the question; "s38 lg no answer is empty"
    # (return "") records no error.
    state = run("adds_nothing")

    assert state.metadata["agent_error"] == "NoAnswerError: no answer produced"
    assert state.output.completion == ""


def test_an_answer_in_content_blocks_is_their_text(doubles):
    # Witness: "s38 lg content repr" (str(last_ai.content)) answers the list's repr.
    assert run("content_blocks").output.completion == "Paris"


def test_a_final_state_that_is_not_a_dict_reaches_the_output_map_and_without_one_is_no_answer(doubles):
    # Witness: "s38 lg final state assumed dict" (if True) calls .get on the str, an AttributeError.
    mapped = run("str_entrypoint", input_map="to_question", output_map="shouted")
    unmapped = run("str_entrypoint", input_map="to_question")

    assert mapped.output.completion == "PLAIN WORDS"
    assert unmapped.metadata["agent_error"] == "NoAnswerError: no answer produced"


# Interrupt


@pytest.mark.parametrize(
    "factory",
    ["interrupts", "interrupts_without_checkpointer", "interrupts_in_subgraph"],
    ids=["checkpointer", "no-checkpointer", "in-subgraph"],
)
def test_an_interrupted_run_has_an_empty_answer_no_error_and_stores_the_interrupt_value(doubles, factory):
    # The value is stored in memory: only the scrub keeps it out of the log (see the run_task test below).
    # Witnesses: "s38 lg interrupt not detected" (interrupted = False) fails with NoAnswerError; "s38 lg interrupted
    # answer read" (completion always from _answer) does too; "s50 lg interrupt object stored" (i for i.value) stores
    # the Interrupt's repr, id included. "s38 lg interrupt payload stored" is retired: storing is now the intent.
    state = run(factory)

    assert state.metadata["interrupted"] is True
    assert state.metadata["agent_error"] is None
    assert state.output.completion == ""
    assert state.metadata["interrupts"] == [doubles.SECRET]


def test_each_interrupt_in_the_final_state_is_stored_in_order_as_its_value_made_json_safe(doubles):
    # Witnesses: "s50 lg interrupts reversed" swaps the entries; "s50 lg interrupt object stored" stores each
    # Interrupt's repr; "s49 lg json_safe identity" keeps the tuple and the Opaque object.
    state = run("two_interrupts_in_one_state")

    assert state.metadata["interrupted"] is True
    assert state.metadata["interrupts"] == [{"step": "first", "who": ["employee", 7], "what": "opaque(7)"}, "second"]


def test_every_interrupt_of_a_step_with_parallel_interrupts_is_stored(doubles):
    # LangGraph streams each parallel interrupt in its own root "values" chunk; invoke() is the control: it reports
    # both. Their relative order is LangGraph's and not fixed, so it is not asserted here.
    # Witness: "s50 lg interrupts from final only" (collect from the last root chunk alone) loses one of the two.
    raw = doubles.parallel_interrupts().invoke({"messages": []})["__interrupt__"]
    assert sorted(i.value for i in raw) == ["from a", "from b"]

    state = run("parallel_interrupts")

    assert state.metadata["interrupted"] is True
    assert sorted(state.metadata["interrupts"]) == ["from a", "from b"]


def test_an_interrupt_repeated_across_root_chunks_is_stored_once_in_first_seen_order(doubles):
    # Witnesses: "s50 lg interrupts not deduplicated" (append every entry) stores "first" twice; "s50 lg interrupts
    # last seen moves" (pop and re-insert) stores ["second", "first"].
    state = run("repeated_interrupt_across_root_chunks")

    assert state.metadata["interrupted"] is True
    assert state.metadata["interrupts"] == ["first", "second"]


@pytest.mark.parametrize("factory", ["plain_reply", "raises"], ids=["answered", "raised"])
def test_a_run_that_did_not_interrupt_records_interrupted_false_and_no_interrupts_key(doubles, factory):
    # raises fails in its first node, so the run errors before any interrupt.
    # Witnesses: "s38 lg interrupted starts true" leaves True after the exception; "s50 lg interrupts stored
    # unconditionally" adds an empty list.
    state = run(factory)

    assert state.metadata["interrupted"] is False
    assert "interrupts" not in state.metadata


@pytest.mark.parametrize("capture", [True, False], ids=["capture-content", "scrubbed"])
def test_the_interrupt_value_reaches_the_log_only_with_capture_content(doubles, tmp_path, capture):
    # Witness: "s49 scrub keeps interrupts" (interrupts in _SAFE_SAMPLE_METADATA) leaves it in the scrubbed log.
    path = tmp_path / "dataset.jsonl"
    path.write_text(json.dumps({"id": "a", "input": "q", "expect_interrupt": True}), encoding="utf-8")
    task = build_task(path, ref("interrupts"), adapter="langgraph", capture_content=capture)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    log_path = run_task(task, run_dir, capture)

    [sample] = read_eval_log(log_path).samples
    assert sample.scores[CASE_CHECKS].value == CORRECT  # control: the run interrupted as the case expects.
    assert sample.metadata.get("interrupts") == ([doubles.SECRET] if capture else None)
    assert (doubles.SECRET in log_path.read_text(encoding="utf-8")) is capture


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"a": [1, "x", None, True, 1.5]}, {"a": [1, "x", None, True, 1.5]}),
        ("plain", "plain"),
        ({"who": {"what": OPAQUE}}, {"who": {"what": "Opaque()"}}),
        (OPAQUE, "Opaque()"),
        (("employee", 7), ["employee", 7]),
    ],
    ids=["json-unchanged", "str-unchanged", "nested-object-repr", "top-level-object-repr", "tuple-list"],
)
def test_json_safe_keeps_json_data_and_turns_what_json_cannot_hold_into_its_repr(value, expected):
    # Witness: "s49 lg json_safe identity" returns the object and the tuple unchanged.
    assert _json_safe(value) == expected


def test_json_safe_keeps_nan_as_nan():
    # json writes NaN and reads it back, so NaN is not a fallback case. Witness: "s49 lg json_safe NaN rejected"
    # (allow_nan=False) turns the whole value into its repr.
    result = _json_safe({"x": math.nan})

    assert list(result) == ["x"]
    assert isinstance(result["x"], float) and math.isnan(result["x"])


def circular():
    value: dict = {"x": "y"}
    value["self"] = value
    return value


@pytest.mark.parametrize("make", [circular, lambda: {("a", 1): "v"}], ids=["circular", "tuple-key"])
def test_json_safe_falls_back_to_the_whole_value_repr_when_json_cannot_encode_it(make):
    # Witness: "s49 lg json_safe fallback dropped" raises the ValueError or TypeError.
    value = make()

    assert _json_safe(value) == repr(value)


@pytest.mark.parametrize("interrupted", [True, False], ids=["interrupted", "not-interrupted"])
def test_run_checks_is_the_same_with_or_without_interrupts_because_it_reads_interrupted(interrupted):
    # Witness: "s49 run_checks reads interrupts" (metadata.get("interrupted") -> "interrupts") flips both pairs.
    case = Case(id="a", input="q", expect_interrupt=True)
    base = {"agent_error": None, "interrupted": interrupted}

    without = run_checks(case, "", base, show_values=True)
    with_value = run_checks(case, "", {**base, "interrupts": ["approve?"]}, show_values=True)

    assert with_value == without == {"expect_interrupt": None if interrupted else "expected an interrupt"}


@pytest.mark.parametrize(
    ("expect_interrupt", "interrupted", "result"),
    [
        (None, False, "absent"),
        (None, True, "unexpected interrupt"),
        (True, True, None),
        (True, False, "expected an interrupt"),
        (False, False, None),
        (False, True, "unexpected interrupt"),
    ],
    ids=["unset-ran", "unset-interrupted", "true-interrupted", "true-ran", "false-ran", "false-interrupted"],
)
def test_expect_interrupt_check_for_every_combination(expect_interrupt, interrupted, result):
    # "absent": the check is not run at all. Witnesses: "s38 expected interrupt never fails" (if False); "s38 unexpected
    # interrupt never fails" (if False); "s38 interrupt check only when set" (drop 'or interrupted'); "s38 interrupt
    # check only when interrupted" (drop 'case.expect_interrupt is not None or').
    case = Case(id="a", input="q", expect_interrupt=expect_interrupt)

    results = run_checks(case, "", {"agent_error": None, "interrupted": interrupted}, show_values=False)

    assert results.get("expect_interrupt", "absent") == result


# Trajectory


def test_tool_calls_and_results_inside_a_subgraph_invoked_by_a_node_are_collected_in_emission_order(doubles):
    # Witnesses: "s38 lg subgraphs not streamed" (subgraphs=False) loses lookup; "s38 lg values only" (stream_mode
    # ["values"]) loses every call.
    state = run("invoked_subgraph")

    assert calls(state) == [{"name": "lookup", "arguments": {"x": 1}}, {"name": "finish", "arguments": {}}]
    assert tool_results(state) == [("t1", "found"), ("t2", "finished")]
    assert state.output.completion == "done"


def test_a_subgraph_used_directly_as_a_node_keeps_its_tool_messages(doubles):
    state = run("subgraph_node")

    assert state.metadata["agent_error"] is None
    assert calls(state) == [{"name": "lookup", "arguments": {"x": 1}}]
    assert tool_results(state) == [("t1", "found")]


def test_subgraph_tool_calls_survive_an_exception_raised_after_the_subgraph(doubles):
    # Witness: "s38 lg subgraphs not streamed" (as above) records no call.
    state = run("invoked_subgraph_then_raises")

    assert state.metadata["agent_error"] == "Boom: after the subgraph"
    assert calls(state) == [{"name": "lookup", "arguments": {"x": 1}}]
    assert state.metadata["tool_errors"] == [False]


@pytest.mark.parametrize("factory", ["idless_then_idd", "idd_then_idless"], ids=["idless-first", "idd-first"])
def test_an_id_less_message_and_its_copy_with_an_id_count_once_in_calls_results_and_usage(doubles, factory):
    # Usage: the lookup turn (1, 2) once plus the answer (10, 20).
    # Witnesses: "s38 lg idd skips idless keys" (repeat by id only) and "s38 lg idless keys not recorded" fail
    # idless-first; "s38 lg idless never repeat" (repeat = False) fails idd-first.
    state = run(factory)

    assert calls(state) == [{"name": "lookup", "arguments": {"x": 1}}]
    assert tool_results(state) == [("t1", "found")]
    assert state.metadata["usage"] == {"inputTokens": 11, "outputTokens": 22, "totalTokens": 33}


def test_two_messages_with_different_ids_are_both_kept_even_when_they_reuse_a_tool_call_id(doubles):
    # Witness: "s38 lg idd compared by keys" (keys <= keys_idless -> keys <= keys_any) drops the second turn.
    state = run("reused_call_ids")

    assert calls(state) == [{"name": "lookup", "arguments": {"x": 1}}, {"name": "lookup", "arguments": {"x": 2}}]
    assert tool_results(state) == [("call-0", "one"), ("call-0", "two")]


def test_messages_are_collected_from_every_update_key_overwrite_and_single_message_and_none_is_skipped(doubles):
    # Witnesses: "s38 lg messages key only" loses audit; "s38 lg overwrite not unwrapped" loses lookup; "s38 lg single
    # message dropped" loses single; "s38 lg none update not skipped" fails the case with an AttributeError.
    state = run("every_update_value")

    assert state.metadata["agent_error"] is None
    assert [c["name"] for c in calls(state)] == ["audit", "lookup", "single"]
    assert tool_results(state) == [("a1", "logged"), ("t1", "found")]


def test_id_less_ai_messages_without_tool_calls_are_each_counted_in_usage(doubles):
    # Witness: "s38 lg callless messages comparable" (comparable = all(call_ids)) drops both drafts.
    assert run("idless_answers").metadata["usage"] == {"inputTokens": 4, "outputTokens": 6, "totalTokens": 10}


def test_an_id_less_reply_without_tool_calls_from_a_subgraph_node_is_counted_once_in_usage(doubles):
    # The reply reports (1, 2, 3) and is the only message with usage, so once is exactly (1, 2, 3).
    # Witnesses: "s43 lg identity check dropped" and "s43 lg identity not recorded" count it twice, (2, 4, 6).
    state = run("plain_subgraph_node")

    assert state.metadata["agent_error"] is None
    assert state.output.completion == "done"
    assert state.metadata["usage"] == {"inputTokens": 1, "outputTokens": 2, "totalTokens": 3}


def test_two_equal_id_less_replies_from_one_node_are_each_counted_in_usage(doubles):
    # Two (1, 2, 3) replies with equal fields are two messages: (2, 4, 6).
    # Witness: "s43 lg identity by equality" (m in unique) drops the second, giving (1, 2, 3).
    assert run("equal_idless_answers").metadata["usage"] == {"inputTokens": 2, "outputTokens": 4, "totalTokens": 6}


def test_dedupe_keeps_one_id_less_message_object_without_tool_call_passed_twice():
    # Witnesses: "s43 lg identity check dropped" and "s43 lg identity not recorded" keep both.
    reply = AIMessage("done")

    kept = _dedupe([reply, reply])

    assert len(kept) == 1
    assert kept[0] is reply


def test_dedupe_keeps_two_distinct_but_equal_id_less_messages_without_tool_calls():
    # Witness: "s43 lg identity by equality" (m in unique) keeps only the first.
    first, second = AIMessage("same"), AIMessage("same")
    assert first == second  # control: the pair is equal, so only identity tells them apart

    kept = _dedupe([first, second])

    assert [id(m) for m in kept] == [id(first), id(second)]


def test_dedupe_keeps_first_emission_order_when_objects_repeat():
    # Witnesses: "s43 lg dedupe order reversed" (insert(0, m)) gives c, a, b; "s43 lg identity check dropped" keeps
    # all five.
    a, b, c = AIMessage("a"), AIMessage("b"), AIMessage("c")

    kept = _dedupe([b, a, c, a, b])

    assert [id(m) for m in kept] == [id(b), id(a), id(c)]


# Config


def received(doubles, case):
    doubles.RECEIVED.clear()
    state = run("recording", case=case)
    assert state.metadata["agent_error"] is None
    [(graph_input, config, kwargs)] = doubles.RECEIVED
    return graph_input, config, kwargs


def test_the_run_streams_values_and_updates_with_subgraphs_and_only_a_thread_id_without_case_config(doubles):
    # Witnesses: "s38 lg values only" and "s38 lg subgraphs not streamed" change the kwargs; "s38 lg thread id not
    # uuid4" (uuid1); "s38 lg no thread id" drops it.
    graph_input, config, kwargs = received(doubles, {"id": "a", "input": QUESTION})

    assert kwargs == {"stream_mode": ["values", "updates"], "subgraphs": True}
    assert list(config) == ["configurable"] and list(config["configurable"]) == ["thread_id"]
    assert uuid.UUID(config["configurable"]["thread_id"]).version == 4
    assert [(type(m).__name__, m.text) for m in graph_input["messages"]] == [("HumanMessage", QUESTION)]


def test_case_config_is_merged_into_configurable_and_can_override_the_thread_id(doubles):
    # Witnesses: "s38 lg case config dropped"; "s38 lg thread id overrides case config" (order swapped).
    _, merged, _ = received(doubles, {"id": "a", "input": "q", "config": {"user": "u-1", "tier": 2}})
    _, overridden, _ = received(doubles, {"id": "a", "input": "q", "config": {"thread_id": "fixed"}})

    assert {k: v for k, v in merged["configurable"].items() if k != "thread_id"} == {"user": "u-1", "tier": 2}
    assert "thread_id" in merged["configurable"]
    assert overridden == {"configurable": {"thread_id": "fixed"}}


def test_a_solver_used_without_case_metadata_runs_with_no_case_config(doubles):
    # Witness: "s38 lg case metadata required" (state.metadata["case"]) raises KeyError outside the case span.
    _, config, _ = received(doubles, None)

    assert list(config["configurable"]) == ["thread_id"]


def test_each_case_attempt_gets_a_new_thread_so_a_shared_checkpointer_remembers_nothing(doubles):
    # The graph answers with how many messages it saw; a reused thread would also see the earlier attempt's two.
    # Witness: "s38 lg thread id constant" answers "1" then "3".
    answers = [run("counts_messages").output.completion for _ in range(2)]

    assert answers == ["1", "1"]


def test_a_graph_compiled_with_a_checkpointer_runs_with_no_setup(doubles):
    # Witness: "s38 lg no thread id" fails with LangGraph's missing thread_id ValueError.
    state = run("with_checkpointer")

    assert state.metadata["agent_error"] is None
    assert state.output.completion == "saved"


# Dataset fields


def test_expect_interrupt_and_config_are_optional_and_load_from_jsonl(tmp_path):
    # Witnesses: "s38 expect_interrupt required" and "s38 config required" (no default) fail the bare case.
    path = tmp_path / "dataset.jsonl"
    lines = [
        {"id": "bare", "input": "q"},
        {"id": "full", "input": "q", "expect_interrupt": True, "config": {"user": "u-1"}},
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

    bare, full = load_dataset(path)

    assert (bare.expect_interrupt, bare.config) == (None, None)
    assert (full.expect_interrupt, full.config) == (True, {"user": "u-1"})


def test_a_dataset_using_the_new_fields_keeps_format_version_1(doubles, tmp_path):
    # The fields are additive, so v2.0 baselines stay comparable. Witness: "s38 dataset format bumped".
    path = tmp_path / "dataset.jsonl"
    path.write_text(json.dumps({"id": "a", "input": "q", "expect_interrupt": False, "config": {}}), encoding="utf-8")

    task = build_task(path, f"{DOUBLES}:plain_reply", adapter="langgraph")

    assert task.metadata["dataset_format_version"] == DATASET_FORMAT_VERSION == 1


# Map flags need the langgraph adapter


def dataset_file(tmp_path):
    path = tmp_path / "dataset.jsonl"
    path.write_text(json.dumps({"id": "a", "input": "q"}), encoding="utf-8")
    return path


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize("flag", ["--input-map", "--output-map"])
def test_a_map_flag_without_the_langgraph_adapter_exits_2_before_any_run_or_baseline_check(tmp_path, command, flag):
    # check names a missing baseline, which would otherwise be reported (exit 2 without SystemExit) first.
    # Witness: "s38 cli map flags unchecked" (if False) returns from main instead of exiting in the parser.
    argv = [command, str(dataset_file(tmp_path)), "--agent", "pkg:build", flag, "pkg:fn"]
    argv += ["--runs-dir", str(tmp_path / "runs")]
    argv += ["--baseline", str(tmp_path / "no-baseline")] if command == "check" else []

    with pytest.raises(SystemExit) as exited:
        main(argv)

    assert exited.value.code == 2
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("maps", [{"input_map": "pkg:fn"}, {"output_map": "pkg:fn"}], ids=["input", "output"])
def test_build_task_rejects_a_map_with_the_strands_adapter(tmp_path, maps):
    # Witness: "s38 run map adapter unchecked" (if False) tries to load the strands agent instead.
    with pytest.raises(ValueError, match="--input-map and --output-map need --adapter langgraph"):
        build_task(dataset_file(tmp_path), "pkg:build", adapter="strands", **maps)


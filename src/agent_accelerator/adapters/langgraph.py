"""LangGraph adapter: runs a local LangGraph graph (a Pregel, or a StateGraph it compiles) inside an Inspect solver.

Traces come from OpenInference's LangChain instrumentation, which uses OpenInference attribute
names rather than the OpenTelemetry gen_ai conventions Strands emits. Scoring does not read traces.
"""

import json
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from inspect_ai.model import ChatMessageTool
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import ToolCallError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.pregel import Pregel
from langgraph.types import Overwrite
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from pydantic import BaseModel

from agent_accelerator.adapters import load_factory

# The input channel the default mapping writes to. LangGraph has no API naming the add_messages channel, so a
# channel with this key is taken as the conversation; any other state shape needs --input-map.
MESSAGES_CHANNEL = "messages"


class UnsupportedGraphError(TypeError):
    """The factory returned something other than a local LangGraph graph."""


class MissingInputMapError(ValueError):
    """The graph has no messages channel, so the question cannot be passed without --input-map."""


class NoAnswerError(ValueError):
    """The run finished without an answer: no output map, structured_response or AIMessage."""


@solver
def langgraph_agent(agent: str, input_map: str | None = None, output_map: str | None = None) -> Solver:
    """agent: "module:function" returning a fresh langgraph Pregel (any compiled graph) or StateGraph per call.

    input_map: "module:function" turning the question into the graph's input dict (needed without a messages channel).
    output_map: "module:function" turning the final root state into the answer string.
    """
    factory = load_factory(agent)
    to_input = load_factory(input_map) if input_map else None
    to_answer = load_factory(output_map) if output_map else None
    instrumentor = LangChainInstrumentor()
    if not instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.instrument(tracer_provider=trace.get_tracer_provider())
    tracer = trace.get_tracer("agent_accelerator")

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        built = factory()
        # The case's config, read raw: a solver used outside build_task may have no case in its metadata.
        case_config = (state.metadata.get("case") or {}).get("config") or {}
        error: str | None = None
        emitted: list[BaseMessage] = []
        final: Any = None
        interrupts: dict[str, Any] = {}  # by id: parallel interrupts arrive in separate root chunks
        interrupted = False
        with tracer.start_as_current_span(
            "eval_case", attributes={"eval.sample_id": str(state.sample_id), "eval.epoch": state.epoch}
        ) as span:
            try:
                graph = _local_graph(built)
                config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4()), **case_config}}
                # Streaming keeps the partial transcript, so tool calls survive a failed run.
                async for namespace, mode, chunk in graph.astream(
                    _graph_input(graph, state.input_text, to_input),
                    config,
                    stream_mode=["values", "updates"],
                    subgraphs=True,
                ):
                    if mode == "updates":
                        emitted.extend(_update_messages(chunk))
                    elif mode == "values" and namespace == ():
                        final = chunk
                        if isinstance(chunk, dict):
                            for i in chunk.get("__interrupt__", ()):
                                interrupts.setdefault(i.id, i)
                interrupted = isinstance(final, dict) and "__interrupt__" in final
                state.output.completion = "" if interrupted else _answer(final, to_answer)
            except Exception as exc:  # the case fails; the run continues
                error = f"{type(exc).__name__}: {exc}"
                span.record_exception(exc)
        # De-duplicated only now: LangGraph assigns message ids in place when its reducer runs, after the event.
        messages = _dedupe(emitted)
        ai_messages = [m for m in messages if isinstance(m, AIMessage)]
        state.metadata["agent_error"] = error
        state.metadata["interrupted"] = interrupted
        if interrupted:  # payload data: the scrub drops it unless --capture-content
            state.metadata["interrupts"] = [_json_safe(i.value) for i in interrupts.values()]
        state.metadata["tool_calls"] = [
            {"name": call["name"], "arguments": call["args"]} for m in ai_messages for call in m.tool_calls
        ]
        state.metadata["tool_errors"] = _tool_errors(ai_messages, messages)
        state.metadata["usage"] = _usage(ai_messages)
        state.metadata["model_id"] = next((m.response_metadata.get("model_name") for m in ai_messages), None)
        state.messages.extend(_tool_messages(messages))
        return state

    return solve


def _local_graph(built: Any) -> Pregel:
    if isinstance(built, StateGraph):
        return built.compile()
    if isinstance(built, Pregel):
        return built
    raise UnsupportedGraphError("not a local LangGraph graph; deployed agents are not supported")


def _graph_input(graph: Pregel, question: str, to_input: Callable[..., Any] | None) -> Any:
    if to_input is not None:
        mapped = to_input(question)
        if not isinstance(mapped, dict):
            raise TypeError(f"--input-map must return a dict, got {type(mapped).__name__}")
        return mapped
    if MESSAGES_CHANNEL not in graph.channels:
        raise MissingInputMapError(
            f"graph has no {MESSAGES_CHANNEL!r} channel; pass --input-map module:function to build its input"
        )
    return {MESSAGES_CHANNEL: [HumanMessage(question)]}


def _answer(final: Any, to_answer: Callable[..., Any] | None) -> str:
    """First that applies: the output map, structured_response, the last AIMessage's text."""
    if to_answer is not None:
        answer = to_answer(final)
        if not isinstance(answer, str):
            raise TypeError(f"--output-map must return a str, got {type(answer).__name__}")
        return answer.strip()
    if isinstance(final, dict):
        structured = final.get("structured_response")
        if structured is not None:
            return _json_text(structured)
        messages = final.get(MESSAGES_CHANNEL)
        if isinstance(messages, list):
            last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
            if last_ai is not None:
                return last_ai.text.strip()
    raise NoAnswerError("no answer produced")


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value)


def _json_safe(value: Any) -> Any:
    """The value as plain JSON data; anything JSON cannot hold as its repr; repr(value) if even that fails."""
    try:
        return json.loads(json.dumps(value, default=repr))
    except (TypeError, ValueError):
        return repr(value)


def _update_messages(chunk: Any) -> list[BaseMessage]:
    """Messages written by the nodes in one "updates" event, from every state key, in emission order."""
    if not isinstance(chunk, dict):
        return []
    found: list[BaseMessage] = []
    for output in chunk.values():  # one entry per node; "__interrupt__" maps to a tuple and is skipped
        for update in output if isinstance(output, list | tuple) else [output]:
            if not isinstance(update, dict):
                continue
            for value in update.values():
                if isinstance(value, Overwrite):
                    value = value.value
                items = value if isinstance(value, list | tuple) else [value]
                found.extend(m for m in items if isinstance(m, BaseMessage))
    return found


def _dedupe(messages: list[BaseMessage]) -> list[AIMessage | ToolMessage]:
    """AI and tool messages once each, in first-emission order: a subgraph's messages reappear in its parent's
    update, sometimes id-less the first time and with an assigned id the second.

    Two messages with ids are the same message only if the ids match. When either has no id, they are compared by
    tool call: a ToolMessage by its tool_call_id, an AIMessage by all of its tool call ids. Ids win where both
    exist because tool call ids are not always unique across turns. The same object seen again is always a repeat:
    a subgraph node's update and the parent's re-emission can share one id-less message with no tool calls.
    """
    seen_objects: set[int] = set()  # id() of every accepted message; the list keeps them alive
    seen_ids: set[str] = set()
    keys_any: set[tuple[str, str]] = set()  # tool call keys of every accepted message
    keys_idless: set[tuple[str, str]] = set()  # tool call keys of accepted messages that had no id
    unique: list[AIMessage | ToolMessage] = []
    for m in messages:
        if isinstance(m, ToolMessage):
            call_ids = [m.tool_call_id]
            kind = "result"
        elif isinstance(m, AIMessage):
            call_ids = [call.get("id") for call in m.tool_calls]
            kind = "call"
        else:
            continue
        keys = {(kind, c) for c in call_ids if c}
        comparable = bool(call_ids) and all(call_ids)  # every tool call id present, so the keys identify it
        if id(m) in seen_objects:
            repeat = True
        elif m.id:
            repeat = m.id in seen_ids or (comparable and keys <= keys_idless)
        else:
            repeat = comparable and keys <= keys_any
        if repeat:
            continue
        unique.append(m)
        seen_objects.add(id(m))
        keys_any.update(keys)
        if m.id:
            seen_ids.add(m.id)
        else:
            keys_idless.update(keys)
    return unique


def _tool_messages(messages: list[Any]) -> list[ChatMessageTool]:
    """One Inspect tool message per ToolMessage, in transcript order, for the judge; the scrub drops them."""
    return [
        ChatMessageTool(
            content=m.text,
            tool_call_id=m.tool_call_id,
            function=m.name,
            error=ToolCallError("unknown", m.text) if m.status == "error" else None,
        )
        for m in messages
        if isinstance(m, ToolMessage)
    ]


def _tool_errors(ai_messages: list[AIMessage], messages: list[Any]) -> list[bool | None]:
    """Per call, in tool_calls order: whether its ToolMessage had status "error"; None when no result arrived.

    Calls reusing an id take that id's results in transcript order, one each, so the nth call gets the nth result.
    """
    pending: dict[str, deque[str]] = defaultdict(deque)
    for m in messages:
        if isinstance(m, ToolMessage):
            pending[m.tool_call_id].append(m.status)
    errors: list[bool | None] = []
    for m in ai_messages:
        for call in m.tool_calls:
            queue = pending.get(call.get("id") or "")
            errors.append(queue.popleft() == "error" if queue else None)
    return errors


def _usage(messages: list[AIMessage]) -> dict[str, int] | None:
    # LangChain leaves usage_metadata as None when the provider reports nothing, so None means unavailable.
    reported = [m.usage_metadata for m in messages if m.usage_metadata is not None]
    if not reported:
        return None
    return {
        "inputTokens": sum(u["input_tokens"] for u in reported),
        "outputTokens": sum(u["output_tokens"] for u in reported),
        "totalTokens": sum(u["total_tokens"] for u in reported),
    }

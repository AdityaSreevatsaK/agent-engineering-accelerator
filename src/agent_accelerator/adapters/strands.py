"""AWS Strands adapter: runs a Strands Agent for each case inside an Inspect solver."""

import json
from collections import defaultdict, deque
from typing import Any

from inspect_ai.model import ChatMessageTool
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import ToolCallError
from opentelemetry import trace

from agent_accelerator.adapters import load_factory


@solver
def strands_agent(agent: str) -> Solver:
    """agent: "module:function" returning a fresh strands.Agent per call."""
    factory = load_factory(agent)
    tracer = trace.get_tracer("agent_accelerator")

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        instance = factory()
        error: str | None = None
        result: Any = None
        with tracer.start_as_current_span(
            "eval_case", attributes={"eval.sample_id": str(state.sample_id), "eval.epoch": state.epoch}
        ) as span:
            try:
                result = await instance.invoke_async(state.input_text)
                state.output.completion = str(result).strip()
            except Exception as exc:  # the case fails; the run continues
                error = f"{type(exc).__name__}: {exc}"
                span.record_exception(exc)
        state.metadata["agent_error"] = error
        state.metadata["tool_calls"] = _tool_calls(instance.messages)
        state.metadata["tool_errors"] = _tool_errors(instance.messages)
        state.metadata["usage"] = _usage(result)
        state.metadata["model_id"] = (instance.model.get_config() or {}).get("model_id")
        state.messages.extend(_tool_messages(instance.messages))
        return state

    return solve


def _tool_messages(messages: list[dict[str, Any]]) -> list[ChatMessageTool]:
    """One Inspect tool message per toolResult block in transcript order, for the judge; the scrub drops them."""
    blocks = [block for message in messages for block in message.get("content", [])]
    names = {block["toolUse"].get("toolUseId"): block["toolUse"]["name"] for block in blocks if "toolUse" in block}
    tool_messages = []
    for block in blocks:
        if "toolResult" not in block:
            continue
        tool_result = block["toolResult"]
        text = _result_text(tool_result.get("content", []))
        tool_messages.append(
            ChatMessageTool(
                content=text,
                tool_call_id=tool_result.get("toolUseId"),
                function=names.get(tool_result.get("toolUseId")),
                error=ToolCallError("unknown", text) if tool_result.get("status") == "error" else None,
            )
        )
    return tool_messages


def _result_text(content: list[dict[str, Any]]) -> str:
    # Text and JSON blocks only; image and document blocks have no text for the judge.
    parts = [b["text"] if "text" in b else json.dumps(b["json"]) for b in content if "text" in b or "json" in b]
    return "\n".join(parts)


def _tool_calls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Read from the in-process transcript, not the trace; traces redact tool arguments by default.
    return [
        {"name": block["toolUse"]["name"], "arguments": block["toolUse"]["input"]}
        for message in messages
        for block in message.get("content", [])
        if "toolUse" in block
    ]


def _tool_errors(messages: list[dict[str, Any]]) -> list[bool | None]:
    """Per call, in _tool_calls order: whether its toolResult had status "error"; None when no result arrived.

    Calls reusing an id take that id's results in transcript order, one each, so the nth call gets the nth result.
    """
    pending: dict[str, deque[str | None]] = defaultdict(deque)
    for message in messages:
        for block in message.get("content", []):
            if "toolResult" in block:
                pending[block["toolResult"]["toolUseId"]].append(block["toolResult"].get("status"))
    errors: list[bool | None] = []
    for message in messages:
        for block in message.get("content", []):
            if "toolUse" in block:
                queue = pending.get(block["toolUse"].get("toolUseId"))
                status = queue.popleft() if queue else None
                errors.append(None if status is None else status == "error")
    return errors


def _usage(result: Any) -> dict[str, int] | None:
    # Strands reports zeros when the provider sent no usage, so all-zero is treated as unavailable.
    if result is None:
        return None
    usage = result.metrics.accumulated_usage
    counts = {k: int(usage.get(k, 0)) for k in ("inputTokens", "outputTokens", "totalTokens")}
    return counts if any(counts.values()) else None

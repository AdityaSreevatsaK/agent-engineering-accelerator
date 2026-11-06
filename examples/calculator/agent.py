"""Strands version of the calculator agent, driven by a deterministic, rule-based model double.

The double behaves like a model: it decides whether to call the tool, then answers from the tool
result, so the real Strands loop, tool execution and tracing all run offline.
build_broken_agent() seeds a regression (see rules.BROKEN_OPERATIONS).
build_flaky_agent() seeds it on every second sight of the same question, imitating a live model; run it with --epochs.
"""

import json
from collections import Counter
from collections.abc import AsyncIterable
from typing import Any

from strands import Agent, tool
from strands.models.model import Model

from examples.calculator.rules import (
    BROKEN_OPERATIONS,
    OPERATIONS,
    SYSTEM_PROMPT,
    ToolRequest,
    answer,
    calculate,
    decide,
)


@tool
def calculator(a: float, b: float, op: str) -> float:
    """Apply a basic arithmetic operation.

    Args:
        a: Left operand.
        b: Right operand.
        op: One of add, sub, mul, div.
    """
    return calculate(a, b, op)


class RuleBasedModel(Model):
    def __init__(self, operations: dict[str, str]) -> None:
        self._operations = operations
        self._config: dict[str, Any] = {"model_id": "rule-based-double"}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # type: ignore[override]
        raise NotImplementedError("structured output is not used by this example")

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[Any]:  # type: ignore[override]
        question = next(block["text"] for block in messages[0]["content"] if "text" in block)
        tool_result = next((block["toolResult"] for block in messages[-1]["content"] if "toolResult" in block), None)
        yield {"messageStart": {"role": "assistant"}}
        if tool_result is not None:
            output = " ".join(block.get("text", "") for block in tool_result["content"]).strip()
            reply: ToolRequest | str = answer(question, output, failed=tool_result["status"] == "error")
        else:
            reply = decide(question, self._operations)
        if isinstance(reply, ToolRequest):
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "call-1", "name": "calculator"}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(reply.arguments)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return
        yield {"contentBlockDelta": {"delta": {"text": reply}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


_seen: Counter[str] = Counter()  # per process: one run, every epoch


class FlakyModel(RuleBasedModel):
    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[Any]:  # type: ignore[override]
        if len(messages) == 1:  # first turn: decide this attempt's behaviour
            question = next(block["text"] for block in messages[0]["content"] if "text" in block)
            _seen[question] += 1
            self._operations = BROKEN_OPERATIONS if _seen[question] % 2 == 0 else OPERATIONS
        async for event in super().stream(messages, tool_specs, system_prompt, **kwargs):
            yield event


def _build(operations: dict[str, str], model_class: type[RuleBasedModel] = RuleBasedModel) -> Agent:
    model = model_class(operations)
    return Agent(model=model, tools=[calculator], system_prompt=SYSTEM_PROMPT, callback_handler=None)


def build_agent() -> Agent:
    return _build(OPERATIONS)


def build_broken_agent() -> Agent:
    return _build(BROKEN_OPERATIONS)


def build_flaky_agent() -> Agent:
    return _build(OPERATIONS, FlakyModel)

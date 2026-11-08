"""Strands version of the order-support agent, driven by a deterministic, rule-based model double.

The double replays the transcript on every turn, so multi-step plans run through the real Strands loop.
build_broken_agent() seeds a regression: refunds skip the eligibility policy.
"""

import json
from collections.abc import AsyncIterable
from typing import Any

from strands import Agent, tool
from strands.models.model import Model

from examples.orders import rules
from examples.orders.rules import SYSTEM_PROMPT, ToolRequest, ToolResult, next_step


@tool
def find_customer(email: str) -> str:
    """Look up a customer by email. Returns JSON with customer_id, name and order_ids (oldest first).

    Args:
        email: Customer email address.
    """
    return rules.find_customer(email)


@tool
def get_order(order_id: str) -> str:
    """Look up an order. Returns JSON with order_id, status, total, items and delivered_days_ago.

    Args:
        order_id: Order identifier.
    """
    return rules.get_order(order_id)


@tool
def issue_refund(order_id: str, amount: float) -> str:
    """Refund an order. Returns JSON with refund_id and amount.

    Args:
        order_id: Order identifier.
        amount: Amount to refund, at most the order total.
    """
    return rules.issue_refund(order_id, amount)


def _transcript(messages: list[Any]) -> tuple[str, list[ToolResult]]:
    question = next(block["text"] for block in messages[0]["content"] if "text" in block)
    names: dict[str, str] = {}
    results: list[ToolResult] = []
    for message in messages:
        for block in message["content"]:
            if "toolUse" in block:
                names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            if "toolResult" in block:
                result = block["toolResult"]
                output = " ".join(part.get("text", "") for part in result["content"]).strip()
                results.append(ToolResult(names[result["toolUseId"]], result["status"] == "success", output))
    return question, results


class RuleBasedModel(Model):
    def __init__(self, check_policy: bool) -> None:
        self._check_policy = check_policy
        self._config: dict[str, Any] = {"model_id": "rule-based-double"}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # type: ignore[override]
        raise NotImplementedError("structured output is not used by this example")

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[Any]:  # type: ignore[override]
        question, results = _transcript(messages)
        reply = next_step(question, results, self._check_policy)
        yield {"messageStart": {"role": "assistant"}}
        if isinstance(reply, ToolRequest):
            call = {"toolUseId": f"call-{len(results) + 1}", "name": reply.name}
            yield {"contentBlockStart": {"start": {"toolUse": call}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(reply.arguments)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return
        yield {"contentBlockDelta": {"delta": {"text": reply}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


def _build(check_policy: bool) -> Agent:
    return Agent(
        model=RuleBasedModel(check_policy),
        tools=[find_customer, get_order, issue_refund],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


def build_agent() -> Agent:
    return _build(check_policy=True)


def build_broken_agent() -> Agent:
    return _build(check_policy=False)

"""Template written by `aea init`: replace the tool and prompt with your agent's, keep build_agent's shape.

The factory must return a fresh agent on every call (one per case attempt), so no state leaks between cases.
build_agent runs on Bedrock (needs AWS credentials); AEA_MODEL_ID picks the model. build_offline_agent swaps in a
deterministic, rule-based model double so the same tool, prompt and dataset run with no credentials.
For a LangGraph agent, return a compiled graph with a "messages" state instead and run with --adapter langgraph
(see examples/calculator).
"""

import json
import os
import re
from collections.abc import AsyncIterable
from typing import Any

from strands import Agent, tool
from strands.models import BedrockModel
from strands.models.model import Model

SYSTEM_PROMPT = """You answer questions about office opening hours. Always use the opening_hours tool; never guess.
Reply with only the hours, for example: 09:00-17:00. If the tool reports an unknown office, say the office is unknown.
If the question is not about opening hours, do not call the tool; say you can only help with opening hours."""

_HOURS = {"london": "09:00-17:30", "bangalore": "09:30-18:30"}


@tool
def opening_hours(office: str) -> str:
    """Look up an office's opening hours.

    Args:
        office: Office city name.
    """
    hours = _HOURS.get(office.strip().casefold())
    if hours is None:
        raise LookupError("unknown office")
    return hours


def build_agent() -> Agent:
    model = BedrockModel(model_id=os.environ.get("AEA_MODEL_ID", "us.anthropic.claude-haiku-5-5"))
    return Agent(model=model, tools=[opening_hours], system_prompt=SYSTEM_PROMPT, callback_handler=None)


class OfflineModel(Model):
    """Follows SYSTEM_PROMPT by rule: call the tool for "the <city> office", then answer from its result."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {"model_id": "offline-double"}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # type: ignore[override]
        raise NotImplementedError("structured output is not used by this template")

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[Any]:  # type: ignore[override]
        question = next(block["text"] for block in messages[0]["content"] if "text" in block)
        result = next((block["toolResult"] for block in messages[-1]["content"] if "toolResult" in block), None)
        office = re.search(r"\bthe (\w+) office\b", question, re.IGNORECASE)
        yield {"messageStart": {"role": "assistant"}}
        if result is None and office is not None:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "call-1", "name": "opening_hours"}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps({"office": office.group(1)})}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return
        if result is None:
            reply = "I can only help with opening hours."
        elif result["status"] == "error":
            reply = "The office is unknown."
        else:
            reply = " ".join(block.get("text", "") for block in result["content"]).strip()
            if "json" in question.casefold():
                reply = json.dumps({"hours": reply})
        yield {"contentBlockDelta": {"delta": {"text": reply}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


def build_offline_agent() -> Agent:
    return Agent(model=OfflineModel(), tools=[opening_hours], system_prompt=SYSTEM_PROMPT, callback_handler=None)

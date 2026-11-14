"""Standalone synthetic equipment-support Strands app; no AEA-specific imports.

The deterministic model double exercises the actual Strands tool loop. A broken
factory intentionally treats expired warranties as active for a quality-gate test.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Any

from strands import Agent, tool
from strands.models.model import Model

ASSETS: dict[str, tuple[str, bool]] = {
    "EQ-201": ("laptop", True),
    "EQ-202": ("router", False),
    "EQ-203": ("monitor", True),
    "EQ-204": ("server", False),
    "EQ-205": ("printer", True),
    "EQ-206": ("switch", False),
    "EQ-207": ("scanner", True),
    "EQ-208": ("tablet", False),
    "EQ-209": ("workstation", True),
    "EQ-210": ("firewall", False),
}


@tool
def find_equipment(asset_id: str) -> str:
    """Return details for an equipment item.

    Args:
        asset_id: Equipment identifier, such as EQ-201.
    """
    if asset_id not in ASSETS:
        raise ValueError("equipment not found")
    return json.dumps({"asset_id": asset_id, "type": ASSETS[asset_id][0]})


@tool
def check_warranty(asset_id: str) -> str:
    """Check whether an equipment item's warranty is active.

    Args:
        asset_id: Equipment identifier, such as EQ-201.
    """
    if asset_id not in ASSETS:
        raise ValueError("equipment not found")
    return json.dumps({"asset_id": asset_id, "active": ASSETS[asset_id][1]})


@dataclass(frozen=True)
class NextTool:
    name: str
    arguments: dict[str, str]


def next_step(question: str, results: list[tuple[str, bool, str]], ignore_expiry: bool = False) -> NextTool | str:
    match = re.search(r"\bEQ-\d{3}\b", question.upper())
    if match is None:
        return "Provide an equipment ID in EQ-000 format."
    asset_id = match.group()
    if not results:
        return NextTool("find_equipment", {"asset_id": asset_id})
    if results[-1][0] == "find_equipment":
        if not results[-1][1]:
            return f"{asset_id}: equipment not found."
        return NextTool("check_warranty", {"asset_id": asset_id})
    if results[-1][0] != "check_warranty" or not results[-1][1]:
        return f"{asset_id}: warranty check failed."
    active = json.loads(results[-1][2])["active"]
    if active or ignore_expiry:
        return f"{asset_id}: repair covered."
    return f"{asset_id}: warranty expired; repair not covered."


def _read_transcript(messages: list[dict[str, Any]]) -> tuple[str, list[tuple[str, bool, str]]]:
    question = next(block["text"] for block in messages[0]["content"] if "text" in block)
    tool_names: dict[str, str] = {}
    results: list[tuple[str, bool, str]] = []
    for message in messages:
        for block in message["content"]:
            if "toolUse" in block:
                tool_names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            if "toolResult" in block:
                value = block["toolResult"]
                output = " ".join(item.get("text", "") for item in value["content"]).strip()
                results.append((tool_names[value["toolUseId"]], value["status"] == "success", output))
    return question, results


class EquipmentModel(Model):
    def __init__(self, ignore_expiry: bool = False) -> None:
        self.ignore_expiry = ignore_expiry
        self._config: dict[str, Any] = {"model_id": "synthetic-equipment-double"}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    def structured_output(self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any) -> Any:
        raise NotImplementedError("This integration uses plain-text responses.")

    async def stream(
        self, messages: list[dict[str, Any]], tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ) -> AsyncIterable[Any]:
        question, results = _read_transcript(messages)
        action = next_step(question, results, ignore_expiry=self.ignore_expiry)
        yield {"messageStart": {"role": "assistant"}}
        if isinstance(action, NextTool):
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": f"call-{len(results) + 1}", "name": action.name}}
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(action.arguments)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": action}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}


def _build(ignore_expiry: bool) -> Agent:
    return Agent(
        model=EquipmentModel(ignore_expiry),
        tools=[find_equipment, check_warranty],
        system_prompt="Verify equipment and its warranty before confirming repair coverage.",
        callback_handler=None,
    )


def build_agent() -> Agent:
    return _build(ignore_expiry=False)


def build_broken_agent() -> Agent:
    return _build(ignore_expiry=True)

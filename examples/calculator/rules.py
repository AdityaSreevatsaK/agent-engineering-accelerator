"""Framework-independent parts of the calculator example: the tool logic and the model double's decisions.

Both the Strands and LangGraph versions use these, so they run the same logical task.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

SYSTEM_PROMPT = "You are a calculator. Use the calculator tool for arithmetic."
OPERATIONS = {"plus": "add", "minus": "sub", "times": "mul", "divided by": "div"}
# Seeded regression: the model misreads "minus" as addition.
BROKEN_OPERATIONS = {**OPERATIONS, "minus": "add"}
_EXPRESSION = re.compile(r"(-?\d+(?:\.\d+)?)\s+(plus|minus|times|divided by)\s+(-?\d+(?:\.\d+)?)")


def calculate(a: float, b: float, op: str) -> float:
    if op == "div" and b == 0:
        raise ValueError("cannot divide by zero")
    if op == "div":
        return a / b
    operations = {"add": a + b, "sub": a - b, "mul": a * b}
    if op not in operations:
        raise ValueError(f"unknown operation {op!r}")
    return operations[op]


@dataclass(frozen=True)
class ToolRequest:
    arguments: dict[str, Any]


def _number(text: str) -> int | float:
    value = float(text)
    return int(value) if value.is_integer() else value


def decide(question: str, operations: dict[str, str]) -> ToolRequest | str:
    """First model turn: call the calculator for arithmetic, otherwise reply directly."""
    match = _EXPRESSION.search(question)
    if match is None:
        return "I can only help with arithmetic."
    a, word, b = match.groups()
    return ToolRequest({"a": _number(a), "b": _number(b), "op": operations[word]})


def answer(question: str, tool_output: str, failed: bool) -> str:
    """Second model turn: phrase the tool result."""
    if failed:
        return f"Sorry, that failed: {tool_output}"
    result = _number(tool_output)
    if question.lower().startswith("json:"):
        match = _EXPRESSION.search(question)
        return json.dumps({"result": result, "operation": OPERATIONS[match.group(2)] if match else None})
    return str(result)

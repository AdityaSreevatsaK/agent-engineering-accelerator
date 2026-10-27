"""Deterministic stand-in for a judge model, for offline demos and tests: `--judge mockllm/aea-judge-double`.

Like the example agents' model doubles, it reads the prompt it is given rather than knowing the case. It finds the
data marker in the system message and reads only the blocks carrying that marker from the user message, so text
inside the answer is never taken as an instruction or as a block of its own.

- With a REFERENCE block (golden mode): pass if the answer equals the reference, as JSON when both parse as JSON,
  otherwise as text with whitespace, case and a trailing full stop ignored.
- Without one (reference-free): every criterion listed in the system message passes if the answer is not blank.
  It checks shape, not meaning: it cannot tell a wrong answer from a right one.
- With ANSWER_A and ANSWER_B blocks (pairwise): "same" if the answers are equivalent as above; otherwise the
  non-blank one if exactly one is blank; otherwise "A", the answer shown first. That last rule is a deliberate
  position bias: judged in both orders, it disagrees with itself, so differing answers end as "same" with an order
  disagreement, which is what the swap exists to catch.

A prompt it cannot read gets a reply that is not JSON, which the judge scorer records as a judge error.
"""

import json
import re
from typing import Any

from inspect_ai.model import ChatMessage, ChatMessageSystem, ChatMessageUser, GenerateConfig, ModelOutput
from inspect_ai.tool import ToolChoice, ToolInfo

from agent_accelerator.scorers import normalise

MODEL_NAME = "aea-judge-double"
NOT_UNDERSTOOD = "judge double: prompt not understood"


def _marker(system: str) -> str | None:
    found = re.search(r"<<<BEGIN NAME ([0-9a-f]{16})>>>", system)
    return found.group(1) if found else None


def _block(user: str, name: str, marker: str) -> str | None:
    found = re.search(rf"<<<BEGIN {name} {marker}>>>\n(.*?)\n<<<END {name} {marker}>>>", user, flags=re.DOTALL)
    return found.group(1) if found else None


def _criteria(system: str) -> list[str]:
    return re.findall(r"^- ([a-z][a-z0-9_]*): ", system, flags=re.MULTILINE)


def _equivalent(answer: str, reference: str) -> bool:
    try:
        return json.loads(answer) == json.loads(reference)
    except ValueError:
        return normalise(answer) == normalise(reference)


def _ruling(passed: bool, reason: str) -> dict[str, str]:
    return {"verdict": "pass" if passed else "fail", "reason": reason}


def _pair_verdict(answer_a: str, answer_b: str) -> tuple[str, str]:
    if _equivalent(answer_a, answer_b):
        return "same", "answers are equivalent"
    if bool(answer_a.strip()) != bool(answer_b.strip()):
        return ("A" if answer_a.strip() else "B"), "the other answer is blank"
    return "A", "answers differ; the double prefers the first one shown"


def judge_reply(system: str, user: str) -> str:
    """The double's reply to one judge prompt, as the JSON text a judge model would return."""
    marker = _marker(system)
    if marker is not None:
        answer_a, answer_b = _block(user, "ANSWER_A", marker), _block(user, "ANSWER_B", marker)
        if answer_a is not None and answer_b is not None:
            verdict, reason = _pair_verdict(answer_a, answer_b)
            return json.dumps({"verdict": verdict, "reason": reason})
    answer = _block(user, "ANSWER", marker) if marker else None
    if marker is None or answer is None:
        return NOT_UNDERSTOOD
    reference = _block(user, "REFERENCE", marker)
    if reference is not None:
        same = _equivalent(answer, reference)
        reason = "answer matches the reference" if same else "answer differs from the reference"
        return json.dumps(_ruling(same, reason))
    answered = bool(answer.strip())
    reason = "answer is not blank" if answered else "answer is blank"
    criteria: dict[str, Any] = {name: _ruling(answered, reason) for name in _criteria(system)}
    return json.dumps({"criteria": criteria, **_ruling(answered, reason)})


def judge_double(
    input: list[ChatMessage], tools: list[ToolInfo], tool_choice: ToolChoice, config: GenerateConfig
) -> ModelOutput:
    """mockllm custom_outputs callable."""
    system = next((m.text for m in input if isinstance(m, ChatMessageSystem)), "")
    user = next((m.text for m in input if isinstance(m, ChatMessageUser)), "")
    return ModelOutput.from_content(model=MODEL_NAME, content=judge_reply(system, user))

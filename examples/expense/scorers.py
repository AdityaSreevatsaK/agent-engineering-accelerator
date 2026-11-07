"""Custom scorer for the expense example: `aea run ... --scorer examples.expense.scorers:amounts_grounded`.

amounts_grounded checks that every amount in the reply (the `*_usd` fields; reasons carry no figures) is traceable
to the claim, without re-implementing the policy:

- claimed_usd equals the sum of the claim's lines, each converted to USD at the fixed rates;
- each adjustment's claimed_usd equals its line's converted amount, and its approved_usd lies between 0 and that;
- approved_usd equals the sum of every line's approved amount (adjusted lines as adjusted, the rest in full),
  or 0 for a referral.

A cap remainder is bounded rather than recomputed, so the scorer is not a second copy of the policy engine.
It catches invented figures, wrong conversions and totals that do not add up. A reply that is not JSON fails.
"""

import json
from typing import Any

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState

from examples.expense.rules import USD_RATES

TOLERANCE = 0.005  # half a cent: amounts are rounded to 2 decimal places


def _to_usd(line: dict[str, Any]) -> float | None:
    rate = USD_RATES.get(line["currency"])
    return None if rate is None else round(line["amount"] * rate, 2)


def _same(a: Any, b: float) -> bool:
    return isinstance(a, int | float) and not isinstance(a, bool) and abs(a - b) <= TOLERANCE


def ungrounded(claim: dict[str, Any], reply: dict[str, Any]) -> str | None:
    """The first amount in reply that is not grounded in claim, described; None when all are grounded."""
    usd = [_to_usd(line) for line in claim["lines"]]
    approved = reply.get("approved_usd")
    if reply.get("decision") == "refer":
        if not _same(approved, 0.0):
            return "a referral approves nothing"
    if "claimed_usd" in reply:
        if None in usd:
            return "claimed_usd given for a claim with an unconvertible line"
        if not _same(reply["claimed_usd"], round(sum(u or 0.0 for u in usd), 2)):
            return "claimed_usd is not the converted sum of the lines"
    if reply.get("decision") == "refer":
        return None

    approved_by_line = list(usd)
    for adjustment in reply.get("adjustments", []):
        number = adjustment.get("line")
        if isinstance(number, bool) or not isinstance(number, int):
            return f"adjustment for unknown line {number}"
        if not 1 <= number <= len(usd) or usd[number - 1] is None:
            return f"adjustment for unknown line {number}"
        line_usd = usd[number - 1] or 0.0
        if not _same(adjustment.get("claimed_usd"), line_usd):
            return f"line {number} claimed_usd is not its converted amount"
        line_approved = adjustment.get("approved_usd")
        if isinstance(line_approved, bool) or not isinstance(line_approved, int | float):
            return f"line {number} approved_usd is outside 0..claimed"
        if not 0 <= line_approved <= line_usd + TOLERANCE:
            return f"line {number} approved_usd is outside 0..claimed"
        approved_by_line[number - 1] = line_approved
    if None in approved_by_line:
        return "approved_usd given for a claim with an unconvertible line"
    if not _same(approved, round(sum(a or 0.0 for a in approved_by_line), 2)):
        return "approved_usd is not the sum of the approved lines"
    return None


@scorer(metrics=[accuracy()])
def amounts_grounded():
    async def score(state: TaskState, target: Target) -> Score:
        try:
            claim = json.loads(state.input_text)
            reply = json.loads(state.output.completion)
        except json.JSONDecodeError:
            return Score(value=INCORRECT, explanation="claim or reply is not JSON")
        if not isinstance(reply, dict):
            return Score(value=INCORRECT, explanation="reply is not a JSON object")
        problem = ungrounded(claim, reply)
        return Score(value=INCORRECT if problem else CORRECT, explanation=problem or "all amounts grounded")

    return score

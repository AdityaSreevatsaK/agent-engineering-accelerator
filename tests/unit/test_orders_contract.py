"""Contract checks for the deterministic order-support example."""

from __future__ import annotations

import json
from pathlib import Path

from examples.orders import rules

CASES = Path(__file__).parents[2] / "examples" / "orders" / "dataset.jsonl"


def test_total_spend_example_matches_tool_plan_and_final_answer() -> None:
    rows = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    [case] = [row for row in rows if row["id"] == "total_spend"]
    results: list[rules.ToolResult] = []
    calls: list[dict] = []

    for _ in range(8):
        decision = rules.next_step(case["input"], results)
        if isinstance(decision, str):
            assert decision == case["expected_output"]
            assert calls == case["expected_tool_calls"]
            assert decision == "Carol has spent 17.50 across 2 orders."
            return
        assert isinstance(decision, rules.ToolRequest)
        calls.append({"name": decision.name, "arguments": decision.arguments})
        if decision.name == "find_customer":
            output = rules.find_customer(**decision.arguments)
        elif decision.name == "get_order":
            output = rules.get_order(**decision.arguments)
        else:
            raise AssertionError(f"Unexpected tool: {decision.name}")
        results.append(rules.ToolResult(decision.name, True, output))
    raise AssertionError("Order-support tool plan did not finish")


def test_cancelled_orders_are_excluded_from_spend() -> None:
    assert rules.ORDERS["A104"]["status"] == "cancelled"
    total = sum(
        rules.ORDERS[order_id]["total"]
        for order_id in rules.CUSTOMERS["carol@example.com"]["order_ids"]
        if rules.ORDERS[order_id]["status"] != "cancelled"
    )
    assert total == 17.5

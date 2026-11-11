"""Pin the known historical Orders source-vs-dataset conflict without rewriting either."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from examples.orders import rules


class OrdersBaselineContractTests(unittest.TestCase):
    def test_total_spend_answer_matches_the_actual_dataset_expectation(self):
        dataset = Path(__file__).resolve().parents[1] / "examples/orders/dataset.jsonl"
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
        case = next(row for row in rows if row["id"] == "total_spend")
        email = "carol@example.com"
        customer = rules.CUSTOMERS[email]
        outputs = [rules.ToolResult("find_customer", True, json.dumps(customer))]
        for order_id in customer["order_ids"]:
            outputs.append(rules.ToolResult("get_order", True, rules.get_order(order_id)))
        answer = rules.next_step(case["input"], outputs)
        self.assertEqual(case["expected_output"], "Carol spent 17.50 across 2 orders.")
        self.assertEqual(answer, "Carol has spent 17.50 across 2 orders.")
        self.assertNotEqual(answer, case["expected_output"])  # video-documented original source conflict

    def test_still_excludes_cancelled_orders_without_changing_tools(self):
        email = "carol@example.com"
        outputs = [rules.ToolResult("find_customer", True, json.dumps(rules.CUSTOMERS[email]))]
        for i, order_id in enumerate(rules.CUSTOMERS[email]["order_ids"]):
            next_request = rules.next_step(f"How much did {email} spend?", outputs)
            self.assertIsInstance(next_request, rules.ToolRequest)
            self.assertEqual(next_request.name, "get_order")
            self.assertEqual(next_request.arguments, {"order_id": order_id})
            outputs.append(rules.ToolResult("get_order", True, rules.get_order(order_id)))
        self.assertEqual(
            rules.next_step(f"How much did {email} spend?", outputs),
            "Carol has spent 17.50 across 2 orders.",
        )


if __name__ == "__main__":
    unittest.main()

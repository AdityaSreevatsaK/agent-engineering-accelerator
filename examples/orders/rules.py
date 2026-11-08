"""Framework-independent parts of the order-support example: the store, the tools' logic and the model double's plan.

Unlike the calculator, this task uses several tools, chains them (one tool's output decides the next call),
has a policy that forbids a tool call, and gets tool errors for unknown records.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

SYSTEM_PROMPT = (
    "You are an order support assistant. Use the tools to look up customers and orders. "
    "Refund only orders delivered within the last 30 days."
)
REFUND_WINDOW_DAYS = 30

CUSTOMERS: dict[str, dict[str, Any]] = {
    "alice@example.com": {"customer_id": "C1", "name": "Alice", "order_ids": ["A100"]},
    "bob@example.com": {"customer_id": "C2", "name": "Bob", "order_ids": ["A101", "A102"]},
    "carol@example.com": {"customer_id": "C3", "name": "Carol", "order_ids": ["A103", "A104", "A105"]},
}
ORDERS: dict[str, dict[str, Any]] = {
    "A100": {"status": "shipped", "total": 40.0, "items": ["kettle"], "delivered_days_ago": None},
    "A101": {"status": "delivered", "total": 25.5, "items": ["mug", "tea"], "delivered_days_ago": 45},
    "A102": {"status": "delivered", "total": 12.0, "items": ["spoon"], "delivered_days_ago": 3},
    "A103": {"status": "delivered", "total": 10.0, "items": ["filter"], "delivered_days_ago": 10},
    "A104": {"status": "cancelled", "total": 5.0, "items": ["lid"], "delivered_days_ago": None},
    "A105": {"status": "processing", "total": 7.5, "items": ["jar"], "delivered_days_ago": None},
}


# Tool logic. Error messages carry no user data, because exception text is kept in traces.
def find_customer(email: str) -> str:
    if email not in CUSTOMERS:
        raise LookupError("customer not found")
    return json.dumps(CUSTOMERS[email])


def get_order(order_id: str) -> str:
    if order_id not in ORDERS:
        raise LookupError("order not found")
    return json.dumps({"order_id": order_id, **ORDERS[order_id]})


def issue_refund(order_id: str, amount: float) -> str:
    if order_id not in ORDERS:
        raise LookupError("order not found")
    if amount > ORDERS[order_id]["total"]:
        raise ValueError("refund exceeds order total")
    return json.dumps({"refund_id": f"R-{order_id}", "amount": amount})


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    output: str


def refusal_reason(order: dict[str, Any]) -> str | None:
    if order["status"] != "delivered":
        return "it has not been delivered"
    if order["delivered_days_ago"] > REFUND_WINDOW_DAYS:
        return f"it was delivered more than {REFUND_WINDOW_DAYS} days ago"
    return None


_REFUND = re.compile(r"refund order (\w+)", re.IGNORECASE)
_SUMMARY = re.compile(r"^json: summary of order (\w+)", re.IGNORECASE)
_LATEST = re.compile(r"latest order for (\S+@[\w.]+\w)", re.IGNORECASE)
_SPEND = re.compile(r"how much did (\S+@[\w.]+\w) spend", re.IGNORECASE)
_STATUS = re.compile(r"order (\w+)", re.IGNORECASE)
NOT_FOUND_CUSTOMER = "I could not find a customer with that email."


def next_step(question: str, results: list[ToolResult], check_policy: bool = True) -> ToolRequest | str:
    """One model turn: the next tool call, or the final reply once the plan is complete.

    check_policy=False seeds the regression: refunds are issued without checking eligibility.
    """
    if match := _REFUND.search(question):
        return _refund(match.group(1), results, check_policy)
    if match := _SUMMARY.search(question):
        return _with_order(match.group(1), results, _summary)
    if match := _LATEST.search(question):
        return _latest(match.group(1), results)
    if match := _SPEND.search(question):
        return _spend(match.group(1), results)
    if match := _STATUS.search(question):
        return _with_order(match.group(1), results, lambda order: f"Order {order['order_id']} is {order['status']}.")
    return "I can only help with orders."


def _with_order(order_id: str, results: list[ToolResult], reply) -> ToolRequest | str:
    if not results:
        return ToolRequest("get_order", {"order_id": order_id})
    if not results[0].ok:
        return f"I could not find order {order_id}."
    return reply(json.loads(results[0].output))


def _summary(order: dict[str, Any]) -> str:
    keys = {"order_id": order["order_id"], "status": order["status"], "total": order["total"]}
    return json.dumps({**keys, "item_count": len(order["items"])})


def _refund(order_id: str, results: list[ToolResult], check_policy: bool) -> ToolRequest | str:
    if not results:
        return ToolRequest("get_order", {"order_id": order_id})
    if not results[0].ok:
        return f"I could not find order {order_id}."
    order = json.loads(results[0].output)
    if len(results) == 1:
        reason = refusal_reason(order) if check_policy else None
        if reason:
            return f"Order {order_id} is not eligible for a refund because {reason}."
        return ToolRequest("issue_refund", {"order_id": order_id, "amount": order["total"]})
    if not results[1].ok:
        return f"Sorry, the refund for order {order_id} failed."
    refund = json.loads(results[1].output)
    return f"Refunded {refund['amount']:.2f} for order {order_id} (refund {refund['refund_id']})."


def _latest(email: str, results: list[ToolResult]) -> ToolRequest | str:
    if not results:
        return ToolRequest("find_customer", {"email": email})
    if not results[0].ok:
        return NOT_FOUND_CUSTOMER
    if len(results) == 1:
        return ToolRequest("get_order", {"order_id": json.loads(results[0].output)["order_ids"][-1]})
    order = json.loads(results[1].output)
    return f"Your latest order {order['order_id']} is {order['status']}."


def _spend(email: str, results: list[ToolResult]) -> ToolRequest | str:
    """Looks up every order in turn, then totals those not cancelled."""
    if not results:
        return ToolRequest("find_customer", {"email": email})
    if not results[0].ok:
        return NOT_FOUND_CUSTOMER
    customer = json.loads(results[0].output)
    fetched = len(results) - 1
    if fetched < len(customer["order_ids"]):
        return ToolRequest("get_order", {"order_id": customer["order_ids"][fetched]})
    orders = [json.loads(r.output) for r in results[1:] if r.ok]
    counted = [o for o in orders if o["status"] != "cancelled"]
    total = sum(o["total"] for o in counted)
    return f"{customer['name']} has spent {total:.2f} across {len(counted)} orders."

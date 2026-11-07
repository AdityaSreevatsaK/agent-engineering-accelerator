"""Real offline LangGraph smoke of the recovered triage and expense examples.

Uses only their deterministic recorded simulated models and local rules.
The optional AWS live model is NEVER built or invoked. Generated test inputs
are not claimed as recovered triage/expense historical datasets.
"""
from __future__ import annotations

import json
import os

from langchain_core.messages import HumanMessage

from agent_accelerator.adapters import load_factory
from agent_accelerator.config import load_config
from examples.expense import agent as expense
from examples.triage import agent as triage

os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["AWS_ACCESS_KEY_ID"] = ""
os.environ["AWS_SECRET_ACCESS_KEY"] = ""
os.environ["AWS_SESSION_TOKEN"] = ""


def verify_configs() -> None:
    from pathlib import Path

    for name in ("triage", "expense"):
        config = load_config(Path("examples") / name / "aea.toml")
        assert config["adapter"] == "langgraph"
        for key in ("agent", "input_map", "output_map"):
            if key in config:
                fn = load_factory(config[key])
                assert callable(fn), (name, key)
    print("PASS: both recovered historical config references resolve to real callables", flush=True)


def triage_smoke() -> None:
    ticket = "I was charged twice, this is urgent."
    initial = {"message": ticket, "category": "", "priority": "", "reply": "", "trail": []}
    baseline = triage.build_agent().invoke(initial)
    assert (baseline["category"], baseline["priority"]) == ("billing", "high"), baseline
    assert "escalated" in baseline["reply"].lower()
    modified = triage.build_reworded_agent().invoke(initial)
    assert (modified["category"], modified["priority"]) == ("technical", "normal"), modified

    paid = triage.build_agent().invoke({**initial, "message": "Please check invoice INV-1001"})
    assert paid["category"] == "billing"
    assert "paid" in paid["reply"].lower()
    mapped = triage.to_input("Please check invoice INV-1001")
    assert mapped == {"message": "Please check invoice INV-1001"}
    output = json.loads(triage.from_output(paid))
    assert output["category"] == "billing" and output["priority"] == "normal"
    print("PASS: source-recovered LangGraph triage routing, tool calls and custom maps", flush=True)


def expense_smoke() -> None:
    original = {
        "employee_grade": 3,
        "trip": {"city": "London", "days": 2},
        "lines": [
            {"category": "taxi", "currency": "USD", "amount": 50.0, "receipt": True},
            {"category": "meals", "currency": "USD", "amount": 250.0, "receipt": True},
        ],
    }
    result = expense.build_agent().invoke({"messages": [HumanMessage(content=json.dumps(original))]})
    assert result["messages"]
    response = json.loads(result["messages"][-1].content)
    assert response["approved_usd"] == 230.0
    assert response["decision"] == "approve"
    assert response["adjustments"][0]["reason"] == "meals capped at the per diem"

    receipt_case = {
        **original,
        "lines": [
            {"category": "taxi", "currency": "USD", "amount": 100.0, "receipt": False},
        ],
    }
    good = expense.build_agent().invoke({"messages": [HumanMessage(content=json.dumps(receipt_case))]})
    reduced = expense.build_condensed_agent().invoke(
        {"messages": [HumanMessage(content=json.dumps(receipt_case))]}
    )
    good_result = json.loads(good["messages"][-1].content)
    changed_result = json.loads(reduced["messages"][-1].content)
    assert good_result["decision"] == "reject" and good_result["approved_usd"] == 0.0, good_result
    assert changed_result["decision"] == "approve" and changed_result["approved_usd"] == 100.0, changed_result
    print("PASS: source-recovered LangGraph expense tooling, per diem and dropped-receipt regression", flush=True)


def main() -> None:
    verify_configs()
    triage_smoke()
    expense_smoke()
    print("No cloud credentials, provider calls or historical datasets used.", flush=True)


if __name__ == "__main__":
    main()

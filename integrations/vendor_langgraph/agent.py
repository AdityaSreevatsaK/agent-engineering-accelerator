"""Standalone, deterministic LangGraph supplier-onboarding workflow.

Custom state requires explicit --input-map and --output-map when evaluated by AEA.
No AEA internals or other example applications are imported.
"""
from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

# Synthetic values only: (tax registration valid, sanctions hold).
SUPPLIERS = {
    "VN-301": (True, False),
    "VN-302": (False, False),
    "VN-303": (True, True),
    "VN-304": (False, True),
    "VN-305": (True, False),
    "VN-306": (True, True),
    "VN-307": (False, False),
    "VN-308": (True, False),
    "VN-309": (True, False),
    "VN-310": (True, True),
    "VN-311": (True, False),
}


class OnboardingState(TypedDict, total=False):
    vendor_id: str
    registered: bool
    tax_valid: bool
    sanctions_hold: bool
    refusal_reason: str
    response: str


def to_request(question: str) -> dict[str, str]:
    """Adapt the ordinary evaluation question into a custom-state graph input."""
    match = re.search(r"\bVN-\d{3}\b", question.upper())
    return {"vendor_id": match.group() if match else "UNKNOWN"}


def read_decision(state: dict[str, Any]) -> str:
    """Adapt the graph's custom output into AEA's plain-text case answer."""
    return str(state["response"])


def inspect_registration(state: OnboardingState) -> OnboardingState:
    entry = SUPPLIERS.get(state["vendor_id"])
    if entry is None:
        return {"registered": False, "tax_valid": False, "sanctions_hold": False}
    return {"registered": True, "tax_valid": entry[0], "sanctions_hold": entry[1]}


def _make_assessor(skip_sanctions: bool):
    def assess(state: OnboardingState) -> OnboardingState:
        if not state["registered"]:
            return {"refusal_reason": "vendor not found"}
        if not state["tax_valid"]:
            return {"refusal_reason": "tax registration invalid"}
        if state["sanctions_hold"] and not skip_sanctions:
            return {"refusal_reason": "sanctions hold"}
        return {"refusal_reason": ""}
    return assess


def route(state: OnboardingState) -> str:
    return "reject" if state["refusal_reason"] else "approve"


def approve(state: OnboardingState) -> OnboardingState:
    return {"response": f"{state['vendor_id']}: onboarding approved."}


def reject(state: OnboardingState) -> OnboardingState:
    reason = state["refusal_reason"]
    if reason == "vendor not found":
        return {"response": f"{state['vendor_id']}: vendor not found."}
    return {"response": f"{state['vendor_id']}: onboarding denied ({reason})."}


def _build(skip_sanctions: bool) -> CompiledStateGraph:
    graph = StateGraph(OnboardingState)
    graph.add_node("registration", inspect_registration)
    graph.add_node("policy", _make_assessor(skip_sanctions))
    graph.add_node("approve", approve)
    graph.add_node("reject", reject)
    graph.add_edge(START, "registration")
    graph.add_edge("registration", "policy")
    graph.add_conditional_edges("policy", route, {"approve": "approve", "reject": "reject"})
    graph.add_edge("approve", END)
    graph.add_edge("reject", END)
    return graph.compile()


def build_agent() -> CompiledStateGraph:
    return _build(skip_sanctions=False)


def build_broken_agent() -> CompiledStateGraph:
    """Deliberate compliance defect: a sanctions hold no longer blocks onboarding."""
    return _build(skip_sanctions=True)

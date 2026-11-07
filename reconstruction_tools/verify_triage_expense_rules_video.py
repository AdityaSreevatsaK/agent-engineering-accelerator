"""Offline video-provenance and deterministic-behaviour audit of recovered example rules.

Original source from the uploaded 7 November videos. Recorded Notepad++
counts are evidence of transcription consistency, not byte-for-byte proof.
The expense candidate remains two characters shorter than the editor count.
No external providers, network, LangGraph, Inspect AI or paid models used.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = {
    "triage": {
        "sha256": "015c75c537d75dacaad42b27b9365b86c1a8edb405045f45298d295dc2a2e43d",
        "lf_chars": 6467,
        "lf_terminators": 161,
        "editor_crlf_chars": 6628,
        "editor_lines": 162,
        "functions": {
            "lookup_invoice", "search_known_issues", "escalate_to_human",
            "active_rules", "classify",
        },
        "classes": {"Rule"},
    },
    "expense": {
        "sha256": "863b549361d97c36755369da6a9ae974fcd1e465ef4a00924c21068f946b5a90",
        "lf_chars": 9685,
        "lf_terminators": 219,
        "editor_crlf_chars": 9906,
        "editor_lines": 220,
        "functions": {
            "lookup_policy", "convert_currency", "per_diem",
            "active_rules", "parse_claim", "plan", "next_step", "review",
        },
        "classes": {"ToolRequest", "ToolResult"},
    },
}


def source_and_rules(name: str, spec: dict) -> dict:
    path = ROOT / "examples" / name / "rules.py"
    source = path.read_text(encoding="utf-8")  # CRLF-normalised across Windows/Ubuntu
    if not source.endswith("\n"):
        raise AssertionError(f"{name}: recovered source lost terminating newline")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest != spec["sha256"]:
        raise AssertionError(f"{name}: video-derived candidate changed without provenance review")
    if len(source) != spec["lf_chars"] or source.count("\n") != spec["lf_terminators"]:
        raise AssertionError(f"{name}: source text length or physical lines changed")
    if source.count("\n") + 1 != spec["editor_lines"]:
        raise AssertionError(f"{name}: Notepad++ display line count differs")
    delta = len(source) + source.count("\n") - spec["editor_crlf_chars"]
    if delta != (0 if name == "triage" else -2):
        raise AssertionError(f"{name}: video editor character discrepancy changed")
    tree = ast.parse(source, filename=path.as_posix(), feature_version=(3, 11))
    functions = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if not spec["functions"] <= functions or not spec["classes"] <= classes:
        raise AssertionError(f"{name}: video source signatures missing")
    # runpy executes only the literal deterministic rules modules, never
    # the LangGraph agents or optional AWS-backed live constructors.
    rules = runpy.run_path(str(path))
    print(
        f"PASS {name}: {spec['editor_lines']} displayed lines, "
        f"{len(source) + source.count(chr(10)):,} reconstructed CRLF characters; "
        f"editor difference {delta:+d} (0 exact, -2 explicitly provisional)",
        flush=True,
    )
    return rules


def triage_checks(ns: dict) -> None:
    original, reordered = ns["PROMPT"], ns["PROMPT_REWORDED"]
    assert ns["classify"](original, "I was charged twice") == {
        "category": "billing", "priority": "high",
    }
    assert ns["classify"](reordered, "I was charged twice") == {
        "category": "technical", "priority": "normal",
    }
    assert ns["classify"](original, "Invoice INV-1001 was billed")["category"] == "billing"
    assert ns["classify"](original, "Dashboard outage") == {
        "category": "technical", "priority": "high",
    }
    assert ns["classify"](original, "Please reset my password")["category"] == "account"
    assert json.loads(ns["lookup_invoice"]("INV-1002"))["status"] == "refunded"
    assert json.loads(ns["lookup_invoice"]("INV-9999"))["found"] is False
    assert json.loads(ns["search_known_issues"]("CSV export breaks"))[0]["id"] == "KI-42"
    escalation = json.loads(ns["escalate_to_human"]("billing", "high", "charged twice"))
    assert escalation["escalation_id"].startswith("ESC-")
    print("PASS triage: original vs reworded routing regression and deterministic tool results")


def expense_checks(ns: dict) -> None:
    original, condensed = ns["PROMPT"], ns["PROMPT_CONDENSED"]
    assert "receipt" in ns["active_rules"](original)
    assert "receipt" not in ns["active_rules"](condensed)
    assert json.loads(ns["convert_currency"](10, "EUR", "USD"))["amount"] == 10.8
    assert json.loads(ns["per_diem"]("London", 2))["total_usd"] == 180.0
    assert json.loads(ns["lookup_policy"]("lodging"))["limits"]["senior_from_grade"] == 4
    claim = {
        "employee_grade": 3,
        "trip": {"city": "London", "days": 2},
        "lines": [
            {"category": "taxi", "currency": "USD", "amount": 50.0, "receipt": True},
            {"category": "meals", "currency": "USD", "amount": 250.0, "receipt": True},
        ],
    }
    assert ns["parse_claim"]("not json") is None
    actions = ns["plan"](claim, ns["active_rules"](original))
    assert [a.name for a in actions] == ["lookup_policy", "lookup_policy", "per_diem"]
    answers = [
        ns["ToolResult"](a.name, True, ns[a.name](**a.arguments))
        for a in actions
    ]
    actual = json.loads(ns["next_step"](original, json.dumps(claim), answers))
    assert actual["decision"] == "approve" and actual["approved_usd"] == 230.0
    assert actual["adjustments"][0]["reason"] == "meals capped at the per diem"
    print("PASS expense: policy, currencies, per-diem, source-defined request sequence and review")


def main() -> None:
    triage_checks(source_and_rules("triage", CONTRACTS["triage"]))
    expense_checks(source_and_rules("expense", CONTRACTS["expense"]))
    print("Video-derived rules checked offline; exact original video-byte fidelity NOT certified")


if __name__ == "__main__":
    main()

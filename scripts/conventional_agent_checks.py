"""A minimal conventional QA control: direct framework calls, no AEA imports.

For two fixed synthetic application contracts only; not an alternative general
evaluation framework. Modules are imported from the trusted current working
directory. This script neither writes artefacts nor contacts model providers by
itself; application code controls model behaviour.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

EVIDENCE_PREFIX = "CONVENTIONAL_CHECK_RESULT="


def check_case(case: dict[str, Any], actual: str, calls: list[dict[str, Any]]) -> bool:
    """Compare the same expected answers and exact ordered tool calls as the fixtures."""
    if actual.strip() != case["expected_output"]:
        return False
    expected = case.get("expected_tool_calls")
    if expected is None:
        return True
    canonical = [{"name": c["name"], "arguments": c["arguments"]} for c in expected]
    return calls == canonical


def invoke_strands(application: Any, factory: str, question: str) -> tuple[str, list[dict[str, Any]]]:
    """Run a fresh real Strands agent and inspect its native conversation messages."""
    agent = getattr(application, factory)()
    result = agent(question)
    calls: list[dict[str, Any]] = []
    for message in agent.messages:
        for block in message.get("content", ()):
            if "toolUse" in block:
                use = block["toolUse"]
                calls.append({"name": use["name"], "arguments": use["input"]})
    return str(result).strip(), calls


def invoke_langgraph(application: Any, factory: str, question: str) -> tuple[str, list[dict[str, Any]]]:
    """Run a fresh real LangGraph workflow using its own state translation functions."""
    graph = getattr(application, factory)()
    final = graph.invoke(application.to_request(question))
    return application.read_decision(final).strip(), []


def evaluate(framework: str, factory: str, dataset: Path) -> dict[str, Any]:
    if framework not in {"strands", "langgraph"} or factory not in {"build_agent", "build_broken_agent"}:
        raise ValueError("unsupported synthetic control framework or factory")
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("empty or duplicate-id control dataset")
    # Deliberately independent of agent_accelerator: the ordinary application
    # exposes a module named agent from the current working directory.
    application = importlib.import_module("agent")
    run = invoke_strands if framework == "strands" else invoke_langgraph
    failed: list[str] = []
    for case in cases:
        try:
            actual, calls = run(application, factory, case["input"])
            passed = check_case(case, actual, calls)
        except Exception:
            # Keep synthetic evidence bounded to case IDs; never dump payloads.
            passed = False
        if not passed:
            failed.append(case["id"])
    return {
        "framework": framework,
        "factory": factory,
        "case_count": len(cases),
        "passing_case_count": len(cases) - len(failed),
        "failing_case_ids": failed,
        "passed": not failed,
        "control_type": "direct native framework calls and standard-library checks",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", choices=["strands", "langgraph"], required=True)
    parser.add_argument("--factory", choices=["build_agent", "build_broken_agent"], required=True)
    parser.add_argument("--dataset", type=Path, default=Path("dataset.jsonl"))
    args = parser.parse_args()
    sys.path.insert(0, str(Path.cwd()))
    try:
        evidence = evaluate(args.framework, args.factory, args.dataset)
    except (ImportError, OSError, ValueError, KeyError) as exc:
        print(f"control error: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(EVIDENCE_PREFIX + json.dumps(evidence, sort_keys=True))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

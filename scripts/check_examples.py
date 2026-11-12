"""Smoke-test local, deterministic AEA examples using the real CLI."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    (
        "calculator-strands", "examples/calculator/dataset.jsonl", "passed=10/10",
        ["--adapter", "strands", "--agent", "examples.calculator.agent:build_agent"],
    ),
    (
        "calculator-langgraph", "examples/calculator/dataset.jsonl", "passed=10/10",
        ["--adapter", "langgraph", "--agent", "examples.calculator.langgraph_agent:build_agent"],
    ),
    (
        "orders-strands", "examples/orders/dataset.jsonl", "passed=10/11",
        ["--adapter", "strands", "--agent", "examples.orders.agent:build_agent"],
    ),
    (
        "expense-langgraph", "examples/expense/dataset.jsonl", "passed=12/12",
        [
            "--adapter", "langgraph", "--agent", "examples.expense.agent:build_agent",
            "--scorer", "examples.expense.scorers:amounts_grounded",
        ],
    ),
    (
        "triage-langgraph", "examples/triage/dataset.jsonl", "passed=12/12",
        ["--config", "examples/triage/aea.toml"],
    ),
    (
        "policy-rag-langgraph", "examples/policy_rag/dataset.jsonl", "passed=11/11",
        ["--adapter", "langgraph", "--agent", "examples.policy_rag.agent:build_agent"],
    ),
    (
        "helpdesk-langgraph", "examples/helpdesk/dataset.jsonl", "passed=10/10",
        ["--adapter", "langgraph", "--agent", "examples.helpdesk.agent:build_agent"],
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Run the calculator and triage samples only")
    args = parser.parse_args()
    environment = {
        **os.environ,
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "OPENAI_API_KEY": "",
        "AZURE_OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "PYTHONUTF8": "1",
    }
    selected = (SCENARIOS[0], SCENARIOS[4]) if args.quick else SCENARIOS
    with TemporaryDirectory(prefix="aea-local-examples-") as directory:
        for name, dataset, expected, flags in selected:
            run_path = Path(directory) / name
            command = [
                sys.executable, "-m", "agent_accelerator.cli",
                "run", dataset, *flags, "--runs-dir", str(run_path),
                "--max-samples", "1",
            ]
            p = subprocess.run(
                command, cwd=ROOT, env=environment, text=True,
                encoding="utf-8", errors="replace", capture_output=True,
                timeout=300, check=False,
            )
            if p.returncode or expected not in p.stdout:
                print(
                    f"FAIL {name}: expected {expected}, status {p.returncode}\n"
                    f"stdout:\n{p.stdout[-3000:]}\nstderr:\n{p.stderr[-3000:]}",
                    file=sys.stderr,
                )
                return 1
            print(f"PASS {name}: {expected}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Supplementary Orders evaluation against real AEA CLI and native Strands.

This is NOT a substitute for a missing original tests/unit/test_orders.py;
the historical manifest does not list that test. Original rules/agent source
comes from full user videos and the 11-case dataset from an original screenshot.

The good factory must pass every case and the deliberately policy-broken
factory must fail exactly the two ineligible refund cases.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import load_dataset
from reconstruction_tools.verify_orders_original_sources import validate

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "examples" / "orders" / "dataset.jsonl"
REGRESSIONS = {"refund_not_delivered", "refund_outside_window"}


def run(factory: str, root: Path) -> set[str]:
    runs_dir = root / factory
    command = [
        sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET),
        "--adapter", "strands", "--agent", f"examples.orders.agent:{factory}",
        "--runs-dir", str(runs_dir), "--max-samples", "2",
    ]
    env = {
        **os.environ,
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "", "PYTHONUTF8": "1",
    }
    completed = subprocess.run(
        command, cwd=ROOT, env=env, text=True, encoding="utf-8",
        capture_output=True, timeout=240,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"{factory} AEA CLI returned {completed.returncode}:\n"
            f"{completed.stdout[-3000:]}\n{completed.stderr[-5000:]}"
        )
    outputs = list(runs_dir.iterdir())
    if len(outputs) != 1:
        raise AssertionError(f"{factory}: expected one run folder, got {outputs}")
    results = load_results(outputs[0])
    expected = {case.id for case in load_dataset(DATASET)}
    if set(results.cases) != expected:
        raise AssertionError(f"{factory}: missing/extra cases: {set(results.cases) ^ expected}")
    failures = {case_id for case_id, case in results.cases.items() if not case.passed}
    print(f"{factory}: {len(results.cases)} original screenshot cases, failures: {sorted(failures)}")
    return failures


def main() -> None:
    validate()
    assert len(load_dataset(DATASET)) == 11
    with TemporaryDirectory(prefix="aea_orders_") as d:
        p = Path(d)
        correct = run("build_agent", p)
        if correct:
            raise AssertionError(f"Correct Orders policy failed: {sorted(correct)}")
        broken = run("build_broken_agent", p)
        if broken != REGRESSIONS:
            raise AssertionError(
                "Only two intentionally ineligible refunds should fail; "
                f"expected {sorted(REGRESSIONS)}, observed {sorted(broken)}"
            )
    print("PASS: eleven original Orders cases and exactly two seeded refund-policy regressions")


if __name__ == "__main__":
    main()

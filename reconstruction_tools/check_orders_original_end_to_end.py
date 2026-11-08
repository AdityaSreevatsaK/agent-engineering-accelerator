"""Supplementary Orders evaluation against real AEA CLI and native Strands.

This is NOT a substitute for a missing original tests/unit/test_orders.py;
the historical manifest does not list that test. Original rules/agent source
comes from full user videos and the 11-case dataset from an original screenshot.

The original dataset and original rule-source disagree about total_spend:
dataset expects "Carol spent", rules produce "Carol has spent". Preserve both
originals and assert this exact cross-source mismatch independently. Apart
from that one historical discrepancy, the good agent must pass every case;
the deliberately policy-broken agent fails the two additional refunds.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from inspect_ai.log import read_eval_log

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import load_dataset
from reconstruction_tools.verify_orders_original_sources import validate

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "examples" / "orders" / "dataset.jsonl"
REGRESSIONS = {"refund_not_delivered", "refund_outside_window"}
ORIGINAL_SOURCE_CONFLICT = "total_spend"
ACTUAL_SOURCE_REPLY = "Carol has spent 17.50 across 2 orders."
EXPECTED_SCREENSHOT_REPLY = "Carol spent 17.50 across 2 orders."


def run(factory: str, root: Path) -> tuple[set[str], dict[str, str]]:
    runs_dir = root / factory
    command = [
        sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET),
        "--adapter", "strands", "--agent", f"examples.orders.agent:{factory}",
        "--runs-dir", str(runs_dir), "--max-samples", "2", "--capture-content",
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
    log = read_eval_log(results.log_path)
    samples = {str(sample.id): sample for sample in log.samples or []}
    completions = {case_id: sample.output.completion for case_id, sample in samples.items()}
    if set(completions) != expected:
        raise AssertionError(f"{factory}: Inspect completions differ from screenshot case IDs")
    if completions[ORIGINAL_SOURCE_CONFLICT] != ACTUAL_SOURCE_REPLY:
        case = samples[ORIGINAL_SOURCE_CONFLICT]
        print(
            f"ORDERS DIAGNOSTIC {factory}: "
            f"completion={completions[ORIGINAL_SOURCE_CONFLICT]!r}, "
            f"agent_error={case.metadata.get('agent_error')!r}, "
            f"tool_calls={case.metadata.get('tool_calls')!r}, "
            f"tool_errors={case.metadata.get('tool_errors')!r}, "
            f"scores={[(k, v.value, v.explanation) for k, v in case.scores.items()]!r}",
            flush=True,
        )
        raise AssertionError(
            f"{factory}: source-defined original reply unexpectedly changed: "
            f"{completions[ORIGINAL_SOURCE_CONFLICT]!r}"
        )
    print(f"{factory}: {len(results.cases)} original screenshot cases, failures: {sorted(failures)}")
    return failures, completions


def main() -> None:
    validate()
    assert len(load_dataset(DATASET)) == 11
    with TemporaryDirectory(prefix="aea_orders_") as d:
        p = Path(d)
        screenshots = {case.id: case for case in load_dataset(DATASET)}
        if screenshots[ORIGINAL_SOURCE_CONFLICT].expected_output != EXPECTED_SCREENSHOT_REPLY:
            raise AssertionError("Original screenshot expectation changed")
        correct, _ = run("build_agent", p)
        if correct != {ORIGINAL_SOURCE_CONFLICT}:
            raise AssertionError(
                f"Good Orders policy should fail only recorded source conflict: {sorted(correct)}"
            )
        broken, _ = run("build_broken_agent", p)
        if broken != REGRESSIONS | {ORIGINAL_SOURCE_CONFLICT}:
            raise AssertionError(
                "Broken agent must add exactly two ineligible refund failures; "
                f"observed {sorted(broken)}"
            )
    print(
        "PASS: 11 original cases; one documented original dataset-vs-rule wording "
        "conflict, and exactly two additional broken-policy regression failures."
    )


if __name__ == "__main__":
    main()

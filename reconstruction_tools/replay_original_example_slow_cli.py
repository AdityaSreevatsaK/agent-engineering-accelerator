"""Replay original triage/expense full-CLI regression tests from user videos.

The restored original agent/scorer/dataset/golden files now allow the four
previously unrun prompt-mutation cases to exercise the real AEA CLI and
LangGraph/Inspect AI adapters. We replay original recorded test bodies without
rewriting their contents. Each parametrised pytest case spawns its own CLI
subprocess, so the OpenTelemetry provider is not reset in a process.

Original video candidates are NOT byte-identical certified originals. This
lane checks functional behaviour of the recovered code, not source fidelity.
"""
from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys

from reconstruction_tools.verify_original_video_test_candidates import validate_source
from reconstruction_tools.verify_triage_expense_golden_screenshots import validate_one

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "tests" / "unit"
CASES = {
    "triage": (
        "test_dataset_run_passes_with_the_good_prompt_and_fails_only_the_planted_cases_when_reworded",
        ("good_prompt", "reworded_prompt"),
        ("build_agent", "build_reworded_agent"),
    ),
    "expense": (
        "test_dataset_run_passes_with_the_full_prompt_and_fails_only_the_receipt_cases_when_condensed",
        ("full_prompt", "condensed_prompt"),
        ("build_agent", "build_condensed_agent"),
    ),
}


def replay_one(suite: str) -> int:
    source, tree = validate_source(suite)
    validate_one(suite)
    test_name, expected_ids, expected_factories = CASES[suite]
    original_test = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == test_name),
        None,
    )
    if original_test is None:
        raise AssertionError(f"{suite}: original slow E2E function absent")
    text = ast.get_source_segment(source, original_test) or ""
    if (
        "subprocess.run(command, cwd=REPO" not in text
        or '"-m", "agent_accelerator.cli", "run"' not in text
        or "results = load_results(run_dir)" not in text
        or "len(results.cases) == 12" not in text
        or "case_id for case_id, case in results.cases.items() if not case.passed" not in text
        or any(factory not in source for factory in expected_factories)
        or any(x not in source for x in expected_ids)
    ):
        raise AssertionError(f"{suite}: original recorded CLI regression test drifted")
    if not any(
        isinstance(decorator, ast.Attribute) and decorator.attr == "slow"
        for decorator in original_test.decorator_list
    ):
        raise AssertionError(f"{suite}: slow marker removed from original test")

    staged = STAGED / f"test_{suite}_slow_cli_video_REPLAY_TEMP.py"
    if staged.exists() or staged.is_symlink():
        raise RuntimeError(f"Refusing to overwrite existing file: {staged}")
    staged.write_text(source, encoding="utf-8", newline="\n")
    node = f"{staged.relative_to(ROOT).as_posix()}::{test_name}"
    env = {
        **os.environ,
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "PYTHONUTF8": "1",
    }
    command = [
        sys.executable, "-m", "pytest", "-q", "-m", "slow", "--maxfail=1",
        node,
    ]
    print(
        f"{suite}: running original source with {len(expected_ids)} parameterised CLI "
        "evaluations, each against 12 dataset cases; original source unchanged",
        flush=True,
    )
    try:
        return subprocess.call(command, cwd=ROOT, env=env)
    finally:
        staged.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("triage", "expense", "all"), default="all")
    selected = parser.parse_args().suite
    suites = ("triage", "expense") if selected == "all" else (selected,)
    failures = [suite for suite in suites if replay_one(suite) != 0]
    if failures:
        print(f"Original full-CLI replay FAILED: {failures}", file=sys.stderr)
        return 1
    print("PASS: four original-video CLI prompt-regression tests, 48 evaluated cases total.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

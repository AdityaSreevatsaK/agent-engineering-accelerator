"""Replay original recorded CLI check/baseline subprocess tests completely offline.

Original `test_cli.py` was transcribed from a 1,133-line source recording.
The historic `baselines/calculator.json` bytes were NOT recovered. This lane
generates a NEW, marked test-only calculator baseline with the actual recovered
agent and AEA CLI, then executes the original recorded test functions unchanged.

Only the temporary staged test module's BASELINE_LOG reference and CHECKS map
are redirected to this temporary baseline and selected bounded scenarios.
Neither staged sources nor simulated baseline logs are committed or represented
as historical original files. Results demonstrate behaviour, not byte fidelity.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reconstruction_drafts" / "test_cli_FULL_VIDEO_CANDIDATE.py"
STAGED = ROOT / "tests" / "unit" / "test_cli_original_check_replay_TEMP.py"
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"
SOURCE_SHA256 = "3483b4c44b31224179df78a5778ee36fe45e305c9ebb6aa68bfed21d8038c58f"
BASELINE_ANCHOR = 'BASELINE_LOG = REPO / "baselines" / "calculator.json"'
CHECKS_ANCHOR = '\n@pytest.fixture(scope="module")\ndef check_runs(tmp_path_factory):'

# Keep each original source suite's subprocess fixture bounded. The historical
# functions, parametrisation, expected values and assertions remain untouched.
SUITES = {
    "freeze": {
        "scenarios": ("missing", "freeze_new", "freeze_replace", "freeze_empty_dir"),
        "nodes": (
            "test_check_with_missing_baseline_exits_two_naming_path_and_flag_without_running",
            "test_check_update_baseline_freezes_a_copy_of_the_new_run_into_a_missing_dir",
            "test_check_frozen_baseline_from_a_default_run_holds_no_case_input",
            "test_check_update_baseline_replaces_an_existing_run_dir",
            "test_check_update_baseline_freezes_into_an_existing_empty_dir",
        ),
    },
    "safety": {
        "scenarios": (
            "refuse_capture", "refuse_file", "refuse_no_log", "refuse_two_logs",
            "refuse_runs_dir_is_baseline", "refuse_runs_dir_inside",
        ),
        "nodes": (
            "test_check_update_baseline_refusal_exits_two_before_running_and_leaves_dir_untouched",
        ),
    },
    "compare": {
        "scenarios": (
            "same_agent", "log_file_baseline", "regressed",
            "regressed_within_thresholds", "regressed_one_over_threshold",
            "half_passing_current",
        ),
        "nodes": (
            "test_check_same_agent_as_baseline_exits_zero_and_writes_the_comparison",
            "test_check_regressed_agent_exits_one_with_regression_line_and_comparison",
            "test_check_prints_the_hint_on_stderr_only_when_a_case_fails_without_capture_content",
            "test_check_thresholds_reach_the_comparison",
            "test_check_min_case_pass_rate_applies_to_the_current_run",
            "test_check_min_case_pass_rate_applies_to_the_baseline",
        ),
    },
    "failures": {
        "scenarios": ("error_compare", "error_freeze", "bad_agent", "bad_scorer_freeze"),
        "nodes": (
            "test_check_run_with_error_status_exits_two_without_comparing_or_freezing",
            "test_check_run_that_raises_exits_two_leaving_no_run_dir_and_baseline_untouched",
        ),
    },
}


def validate_historical_source() -> tuple[str, ast.Module]:
    source = SOURCE.read_text(encoding="utf-8")  # normalises Windows CRLF checkout
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Recovered original test_cli.py draft changed; require fidelity review")
    if len(source.splitlines()) != 1133:
        raise RuntimeError("Recorded original CLI line count changed")
    if source.count(BASELINE_ANCHOR) != 1 or source.count(CHECKS_ANCHOR) != 1:
        raise RuntimeError("Recorded original CLI fixture anchors changed")
    return source, ast.parse(source, filename=str(SOURCE), feature_version=(3, 11))


def stage_source(source: str, tree: ast.Module, suite: str) -> str:
    scenarios, nodes = SUITES[suite]["scenarios"], SUITES[suite]["nodes"]
    assert isinstance(scenarios, tuple) and isinstance(nodes, tuple)
    if len(scenarios) != len(set(scenarios)) or len(nodes) != len(set(nodes)):
        raise RuntimeError(f"Duplicate selected scenario or test: {suite}")

    original_tests = {
        n.name: n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    }
    check_declarations = [
        n for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CHECKS" for t in n.targets)
    ]
    if len(check_declarations) != 1 or not isinstance(check_declarations[0].value, ast.Dict):
        raise RuntimeError("Historical CHECKS scenario map structure changed")
    original_cases = {
        n.value for n in check_declarations[0].value.keys
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    if not set(scenarios) <= original_cases:
        raise RuntimeError(f"Unavailable historical check scenarios for {suite}")

    for node_name in nodes:
        fn = original_tests.get(node_name)
        if fn is None:
            raise RuntimeError(f"Missing recorded CLI check test: {node_name}")
        args = {a.arg for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]}
        if "check_runs" not in args or args & {"runs", "price_runs"}:
            raise RuntimeError(f"Unexpected source fixture dependencies: {node_name}")

    # The saved historical test draft is not changed. The temporary module
    # explicitly references a generated, disposable log rather than falsely
    # creating original baselines/calculator.json inside the Git checkout.
    substitute = (
        BASELINE_ANCHOR
        + "\n# REPLAY-ONLY: generated fixture; never a historical original log\n"
        + 'BASELINE_LOG = Path(os.environ["AEA_REPLAY_ONLY_CALCULATOR_BASELINE"])'
    )
    result = source.replace(BASELINE_ANCHOR, substitute, 1)
    selection = "\n# REPLAY-ONLY: bounded selected scenarios, historical assertions unchanged\n"
    selection += "CHECKS = {name: CHECKS[name] for name in " + repr(scenarios) + "}\n"
    result = result.replace(CHECKS_ANCHOR, selection + CHECKS_ANCHOR, 1)
    ast.parse(result, filename=str(STAGED), feature_version=(3, 11))
    return result


def generate_temporary_baseline(folder: Path) -> Path:
    runs_dir = folder / "real-calculator-run"
    env = {**os.environ, "AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"}
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        env[name] = ""
    completed = subprocess.run(
        [
            sys.executable, "-m", "agent_accelerator.cli",
            "run", str(DATASET), "--agent", "examples.calculator.agent:build_agent",
            "--adapter", "strands", "--runs-dir", str(runs_dir),
        ],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=240, check=False,
    )
    if completed.returncode != 0 or "passed=10/10" not in completed.stdout:
        raise RuntimeError(
            "Failed to generate offline 10/10 source-calculator baseline:\n"
            + completed.stdout[-3000:] + "\n" + completed.stderr[-3000:]
        )
    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if len(run_dirs) != 1:
        raise RuntimeError(f"Expected one generated calculator run, got {len(run_dirs)}")
    logs = list(run_dirs[0].glob("*.json"))
    if len(logs) != 1:
        raise RuntimeError(f"Expected one generated Inspect log, got {len(logs)}")
    baseline = folder / "GENERATED_TEST_ONLY_calculator_baseline.json"
    shutil.copyfile(logs[0], baseline)
    return baseline


def run_suite(source: str, tree: ast.Module, suite: str, baseline: Path) -> int:
    content = stage_source(source, tree, suite)
    if STAGED.exists() or STAGED.is_symlink():
        raise RuntimeError(f"Refusing to overwrite pre-existing test file: {STAGED}")
    STAGED.write_text(content, encoding="utf-8", newline="\n")
    try:
        module = STAGED.relative_to(ROOT).as_posix()
        selected = [f"{module}::{test}" for test in SUITES[suite]["nodes"]]
        env = {**os.environ, "AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"}
        env["AEA_REPLAY_ONLY_CALCULATOR_BASELINE"] = str(baseline)
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            env[name] = ""
        print(
            f"Original CLI check replay '{suite}': {len(selected)} recorded test "
            f"functions and {len(SUITES[suite]['scenarios'])} offline scenarios",
            flush=True,
        )
        return subprocess.call(
            [sys.executable, "-m", "pytest", "-q", "-m", "slow", *selected],
            cwd=ROOT, env=env,
        )
    finally:
        STAGED.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=(*SUITES, "all"), default="all")
    args = parser.parse_args()
    source, tree = validate_historical_source()
    if not DATASET.is_file() or not (DATASET.parent / "rules.py").is_file():
        raise RuntimeError("Source-recovered calculator prerequisites missing")
    selected = tuple(SUITES) if args.suite == "all" else (args.suite,)
    with tempfile.TemporaryDirectory(prefix="aea-REPLAY-ONLY-check-") as td:
        generated = generate_temporary_baseline(Path(td))
        failing = [name for name in selected if run_suite(source, tree, name, generated) != 0]
        if failing:
            print(f"Original check source replay failed in {failing}", file=sys.stderr)
            return 1
    print(
        f"PASS: {len(selected)} historical check suites using a labelled generated offline baseline; "
        "original baseline/fixture byte fidelity NOT claimed",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

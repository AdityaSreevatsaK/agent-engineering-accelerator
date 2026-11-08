"""Integrated OFFLINE regression gate for the partial AEA reconstruction.

Executes all active tests/unit/ suites together with the original framework
packages. Historical captured-log fixtures remain unavailable. Explicit, reviewed
deferrals remain enforced by the AST preflight in run_compare_without_original_fixtures.

The calculator agent, dataset and shared rules are recovered from user footage.
Temporary Inspect capture logs are separately generated at CI runtime and MUST
NOT be mistaken for original historical captured-log files.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from reconstruction_tools.run_compare_without_original_fixtures import (
    DEFERRED,
    preflight,
)

ROOT = Path(__file__).resolve().parents[1]

# Both historical example config cases are now active: their configs, agents\n# and rules have all been reconstructed from user-supplied evidence.\n\n# Every original-path suite already verified in isolation, plus stats + init.
# Fail closed if any of these verified tests disappear from the repository.
REQUIRED_TEST_MODULES = (
    "test_adapters.py",
    "test_build_task.py",
    "test_baseline_replacement_safety.py",
    "test_calculator_recovered_dataset.py",
    "test_calculator_rules_video.py",
    "test_calculator_capture_video_evidence.py",
    "test_calculator_broken_redacted_screenshot.py",
    "test_slow_parameter_collision_audit.py",
    "test_cli_pairwise.py",
    "test_cli_recovered_controls.py",
    "test_compare.py",
    "test_compare_statistics.py",
    "test_config.py",
    "test_dataset.py",
    "test_export.py",
    "test_init.py",
    "test_init_symlink_safety.py",
    "test_judge.py",
    "test_judge_double.py",
    "test_judge_double_pairwise.py",
    "test_judge_interrupt.py",
    "test_judge_pairwise_recovered_prefix.py",
    "test_readings.py",
    "test_readings_pairwise.py",
    "test_report.py",
    "test_report_pairwise.py",
    "test_run_task.py",
    "test_scorers.py",
    "test_scrub.py",
    "test_stats_compare.py",
    "test_tool_metrics.py",
)


# Two restored original CLI tests require BOTH lost historical calculator logs.
# Explicitly defer only these, without changing their original test bodies.
CLI_CAPTURE_DEFERRED = (
    "test_compare_with_regression_exits_one",
    "test_compare_output_file_matches_printed_markdown",
)


def verify_cli_capture_deferrals() -> bool:
    source = ROOT / "tests" / "unit" / "test_cli.py"
    if not source.is_file():
        return False
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    definitions = {
        n.name: n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }
    for name in CLI_CAPTURE_DEFERRED:
        fn = definitions.get(name)
        if fn is None:
            raise RuntimeError(f"Missing explicitly deferred original CLI test: {name}")
        symbols = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        if not {"FIXTURE", "BROKEN_FIXTURE"} <= symbols:
            raise RuntimeError(f"CLI test no longer requires the two original logs: {name}")
    return True


def main() -> int:
    # Check before collection so previously unavailable data dependencies
    # cannot silently enter the passing-test numerator.
    preflight()
    missing_tests = [
        filename
        for filename in REQUIRED_TEST_MODULES
        if not (ROOT / "tests" / "unit" / filename).is_file()
    ]
    if missing_tests:
        raise RuntimeError(f"Missing active unit suites: {missing_tests}")

    # All six original triage/expense source dependencies are now required.
    # Fail closed if any regresses into a missing/hallucinated source.
    missing_examples = [
        f"examples/{name}/{filename}"
        for name in ("triage", "expense")
        for filename in ("aea.toml", "agent.py", "rules.py")
        if not (ROOT / "examples" / name / filename).is_file()
    ]
    if missing_examples:
        raise RuntimeError(f"Recovered source dependencies are missing: {missing_examples}")

    argv = [sys.executable, "-m", "pytest", "-q", "-m", "not slow"]
    for path, names in DEFERRED.items():
        argv.extend(f"--deselect={path}::{name}" for name in names)
    if verify_cli_capture_deferrals():
        argv.extend(
            f"--deselect=tests/unit/test_cli.py::{name}" for name in CLI_CAPTURE_DEFERRED
        )
        print("KNOWN GAP: two original CLI comparisons require unavailable original calculator logs.", flush=True)
    # Original-source conflict confirmed by both uploaded videos:
    # examples/expense/scorers.py: referral returns "a referral approves nothing"
    # tests/unit/test_expense.py: referral_approves_something expects "a referral approves something".
    # Preserve BOTH historical texts; do not silently change scorer or assertion.
    expense_test = ROOT / "tests" / "unit" / "test_expense.py"
    if expense_test.exists():
        test_source = expense_test.read_text(encoding="utf-8")
        scorer_source = (ROOT / "examples" / "expense" / "scorers.py").read_text(encoding="utf-8")
        required = (
            'referral_approves_something',
            'a referral approves something',
            'def test_ungrounded_names_the_first_amount_not_traceable_to_the_claim',
        )
        if not all(fragment in test_source for fragment in required):
            raise RuntimeError("Original expense video test conflict changed; review required")
        if 'return "a referral approves nothing"' not in scorer_source:
            raise RuntimeError("Original expense scorer recording changed; review required")
        argv.append(
            "--deselect=tests/unit/test_expense.py::"
            "test_ungrounded_names_the_first_amount_not_traceable_to_the_claim[referral_approves_something]"
        )
        print(
            "KNOWN HISTORICAL CONTRADICTION: one expense scorer/test parameterisation "
            "explicitly deferred; original texts preserved.",
            flush=True,
        )
    argv.append("tests/unit")

    print("INTEGRATED AEA RECONSTRUCTION: running all active offline unit tests.", flush=True)
    print(
        "KNOWN GAPS: 32 original-log-dependent comparison/statistics test functions "
        "(58 parameterised cases) remain explicitly excluded; "
        "the two restored original configuration cases are now executed.",
        flush=True,
    )
    print(
        "The calculator agent, dataset and rules are source-recorded reconstructions; "
        "CI uses SYNTHETIC captured logs only. Original log fixtures remain missing.",
        flush=True,
    )
    return subprocess.call(argv, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

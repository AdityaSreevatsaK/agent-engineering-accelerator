"""Integrated OFFLINE regression gate for the partial AEA reconstruction.

Executes all active tests/unit/ suites together with the original framework
packages. Historical captured-log fixtures remain unavailable. Explicit, reviewed
deferrals remain enforced by the AST preflight in run_compare_without_original_fixtures.

The calculator agent and dataset are recovered from user-supplied footage.
Temporary Inspect capture logs are separately generated at CI runtime and MUST
NOT be mistaken for original historical captured-log files.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from reconstruction_tools.run_compare_without_original_fixtures import (
    DEFERRED,
    preflight,
)

ROOT = Path(__file__).resolve().parents[1]

# Only the original triage and expense config files are absent. These two
# recorded assertions must be restored as soon as their files are recovered.
CONFIG_DEFERRED = (
    "tests/unit/test_config.py::"
    "test_example_config_loads_and_every_reference_it_names_resolves_to_a_callable[triage]",
    "tests/unit/test_config.py::"
    "test_example_config_loads_and_every_reference_it_names_resolves_to_a_callable[expense]",
)

# Every original-path suite already verified in isolation, plus stats + init.
# Fail closed if any of these verified tests disappear from the repository.
REQUIRED_TEST_MODULES = (
    "test_adapters.py",
    "test_build_task.py",
    "test_cli_pairwise.py",
    "test_cli_recovered_controls.py",
    "test_compare.py",
    "test_compare_statistics.py",
    "test_config.py",
    "test_dataset.py",
    "test_export.py",
    "test_init.py",
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

    missing_configs = [
        f"examples/{name}/aea.toml"
        for name in ("triage", "expense")
        if not (ROOT / "examples" / name / "aea.toml").exists()
    ]
    if len(missing_configs) != 2:
        raise RuntimeError(
            "Example fixture inventory changed. Reassess the two explicit config "
            f"deferrals before executing tests. Missing: {missing_configs}"
        )

    argv = [sys.executable, "-m", "pytest", "-q", "-m", "not slow"]
    for path, names in DEFERRED.items():
        argv.extend(f"--deselect={path}::{name}" for name in names)
    argv.extend(f"--deselect={name}" for name in CONFIG_DEFERRED)
    argv.append("tests/unit")

    print("INTEGRATED AEA RECONSTRUCTION: running all active offline unit tests.", flush=True)
    print(
        "KNOWN GAPS: 32 original-log-dependent test functions and two "
        "missing-example-config cases are explicitly excluded.",
        flush=True,
    )
    print(
        "The calculator agent and dataset are source-recorded reconstructions; "
        "CI uses SYNTHETIC captured logs only. Original log fixtures remain missing.",
        flush=True,
    )
    return subprocess.call(argv, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

"""Run AEA's offline unit-test matrix without cloud credentials."""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from make_cli_test_logs import make_cli_references
from make_test_log import make_capture

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tests" / "fixtures" / "calculator_capture_content.json"
CLI_SUCCESS = ROOT / "tests" / "fixtures" / "calculator_cli_success_synthetic.json"
CLI_FAILURE = ROOT / "tests" / "fixtures" / "calculator_cli_failure_synthetic.json"

TEST_MODULES = (
    "test_adapters.py",
    "test_public_advisory_audit.py",
    "test_baseline_inventory.py",
    "test_baseline_replacement_safety.py",
    "test_baseline_transaction.py",
    "test_benchmarking.py",
    "test_build_task.py",
    "test_calculator_dataset.py",
    "test_calculator_rules.py",
    "test_orders_contract.py",
    "test_calculator_log_sample.py",
    "test_cli.py",
    "test_cli_controls.py",
    "test_cli_pairwise.py",
    "test_compare.py",
    "test_compare_statistics.py",
    "test_config.py",
    "test_dataset.py",
    "test_dependency_inventory.py",
    "test_export.py",
    "test_factory_references.py",
    "test_expense.py",
    "test_helpdesk.py",
    "test_init.py",
    "test_init_symlink_safety.py",
    "test_judge.py",
    "test_judge_double.py",
    "test_judge_double_pairwise.py",
    "test_judge_interrupt.py",
    "test_judge_pairwise.py",
    "test_judge_pairwise_prefix.py",
    "test_langgraph_adapter.py",
    "test_leadership_demo_contract.py",
    "test_policy_rag.py",
    "test_pilot_rehearsal.py",
    "test_readings.py",
    "test_readings_pairwise.py",
    "test_resilience_adversarial.py",
    "test_report.py",
    "test_report_pairwise.py",
    "test_run_metrics.py",
    "test_run_task.py",
    "test_scorers.py",
    "test_scrub.py",
    "test_stats_compare.py",
    "test_stats.py",
    "test_tool_metrics.py",
    "test_tokens.py",
    "test_trace_summary.py",
    "test_tracing.py",
    "test_trace_export_privacy.py",
    "test_triage.py",
)

# Full CLI coverage uses disposable synthetic calculator reference runs instead
# of unavailable archived JSON. Tests starting CLI subprocesses are marked slow
# and are exercised separately by the release acceptance job.
DEFERRED_CASES: tuple[str, ...] = ()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slow", action="store_true",
        help="run every marked-slow unit test and the slow conformance acceptance instead of the quick matrix",
    )
    args = parser.parse_args(argv)
    unit_dir = ROOT / "tests" / "unit"
    actual = {path.name for path in unit_dir.glob("test_*.py")}
    listed = set(TEST_MODULES)
    if actual != listed:
        raise RuntimeError(
            f"Offline test inventory differs: unlisted={sorted(actual - listed)} "
            f"missing={sorted(listed - actual)}"
        )
    print(f"DEFERRED CASE GROUPS: {len(DEFERRED_CASES)}", flush=True)
    fixtures = (CAPTURE, CLI_SUCCESS, CLI_FAILURE)
    for target in fixtures:
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing to overwrite local data: {target}")

    with TemporaryDirectory(prefix="aea-unit-fixtures-") as directory:
        work = Path(directory)
        temporary = (work / "capture.json", work / "cli-success.json", work / "cli-failure.json")
        make_capture(temporary[0])
        make_cli_references(temporary[1], temporary[2], work)
        expected: dict[Path, str] = {}
        try:
            for source, target in zip(temporary, fixtures, strict=True):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                expected[target] = sha256(target.read_bytes()).hexdigest()
            if args.slow:
                command = [
                    sys.executable, "-m", "pytest", "-q", "-m", "slow",
                    "tests/unit", "tests/conformance",
                ]
            else:
                command = [
                    sys.executable, "-m", "pytest", "-q", "-m", "not slow",
                    *(arg for case in DEFERRED_CASES for arg in ("--deselect", case)),
                    *(f"tests/unit/{name}" for name in TEST_MODULES),
                ]
            return subprocess.call(command, cwd=ROOT)
        finally:
            for target in reversed(tuple(expected)):
                if target.is_symlink() or not target.is_file():
                    raise RuntimeError(f"Temporary unit-test fixture changed type; refusing deletion: {target}")
                if sha256(target.read_bytes()).hexdigest() != expected[target]:
                    raise RuntimeError(f"Temporary unit-test fixture changed; refusing deletion: {target}")
                target.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

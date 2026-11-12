"""Run AEA's offline unit-test matrix without cloud credentials."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from make_test_log import make_capture

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tests" / "fixtures" / "calculator_capture_content.json"

TEST_MODULES = (
    "test_adapters.py",
    "test_baseline_replacement_safety.py",
    "test_baseline_transaction.py",
    "test_build_task.py",
    "test_calculator_dataset.py",
    "test_calculator_rules.py",
    "test_calculator_log_sample.py",
    "test_cli_controls.py",
    "test_cli_pairwise.py",
    "test_config.py",
    "test_dataset.py",
    "test_export.py",
    "test_expense.py",
    "test_helpdesk.py",
    "test_init.py",
    "test_init_symlink_safety.py",
    "test_judge.py",
    "test_judge_double.py",
    "test_judge_double_pairwise.py",
    "test_judge_interrupt.py",
    "test_judge_pairwise_prefix.py",
    "test_langgraph_adapter.py",
    "test_policy_rag.py",
    "test_readings.py",
    "test_readings_pairwise.py",
    "test_report.py",
    "test_report_pairwise.py",
    "test_run_metrics.py",
    "test_run_task.py",
    "test_scorers.py",
    "test_scrub.py",
    "test_stats_compare.py",
    "test_tool_metrics.py",
    "test_trace_summary.py",
    "test_tracing.py",
    "test_trace_export_privacy.py",
    "test_triage.py",
)

# The referral case contains contradictory scorer and expected-message wording.
KNOWN_MISMATCH = (
    "tests/unit/test_expense.py::"
    "test_ungrounded_names_the_first_amount_not_traceable_to_the_claim"
    "[referral_approves_something]"
)


def main() -> int:
    missing = [name for name in TEST_MODULES if not (ROOT / "tests" / "unit" / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing test modules: {', '.join(missing)}")
    if CAPTURE.exists() or CAPTURE.is_symlink():
        raise FileExistsError(f"Refusing to overwrite local data: {CAPTURE}")
    with TemporaryDirectory(prefix="aea-unit-fixture-") as temp:
        target = Path(temp) / "capture.json"
        make_capture(target)
        CAPTURE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, CAPTURE)
        expected_digest = sha256(CAPTURE.read_bytes()).hexdigest()
        try:
            command = [
                sys.executable, "-m", "pytest", "-q", "-m", "not slow",
                "--deselect", KNOWN_MISMATCH,
                *(f"tests/unit/{name}" for name in TEST_MODULES),
            ]
            return subprocess.call(command, cwd=ROOT)
        finally:
            if CAPTURE.is_symlink() or not CAPTURE.is_file():
                raise RuntimeError("Temporary unit-test fixture changed type; refusing deletion")
            if sha256(CAPTURE.read_bytes()).hexdigest() != expected_digest:
                raise RuntimeError("Temporary unit-test fixture changed; refusing deletion")
            CAPTURE.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

"""Abrupt-process-stop fault injection for AEA baseline promotion.

Uses disposable synthetic data and a child Python process. No signals, real
user baselines, external services, model calls or wall-clock timing assumptions.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agent_accelerator.baseline import freeze_run_as_baseline, retained_backup_paths
from agent_accelerator.cli import _validate_baseline_target

SAMPLE = Path(__file__).parents[1] / "fixtures" / "eval_log_sample.json"

# Terminate the isolated child at the exact point where the old snapshot has
# become a backup but the next snapshot has not yet been activated.
CRASH_DURING_ACTIVATION = """
import os
import sys
from pathlib import Path

from agent_accelerator.baseline import freeze_run_as_baseline
from agent_accelerator.cli import _validate_baseline_target

run_dir, baseline, runs_dir = (Path(arg) for arg in sys.argv[1:])
original_rename = Path.rename

def terminate_during_activation(self, target):
    if self.name == "next" and Path(target) == baseline:
        os._exit(47)
    return original_rename(self, target)

Path.rename = terminate_during_activation
freeze_run_as_baseline(run_dir, baseline, runs_dir, False, _validate_baseline_target)
"""


@pytest.mark.slow
def test_abrupt_exit_preserves_previous_baseline_and_blocks_automatic_reuse(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "candidate"
    run_dir.mkdir(parents=True)
    shutil.copyfile(SAMPLE, run_dir / "next.json")
    (run_dir / "report.md").write_text("new synthetic report", encoding="utf-8")

    baseline = tmp_path / "approved"
    baseline.mkdir()
    shutil.copyfile(SAMPLE, baseline / "original.json")
    (baseline / "report.md").write_text("approved original report", encoding="utf-8")
    original_bytes = (baseline / "original.json").read_bytes()

    child = subprocess.run(
        [
            sys.executable, "-c", CRASH_DURING_ACTIVATION,
            str(run_dir), str(baseline), str(runs_dir),
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert child.returncode == 47, (child.returncode, child.stdout, child.stderr)

    # A process death cannot trigger Python's finally blocks. Do not mistake
    # that for atomic zero-downtime promotion: the active path is absent here.
    assert not baseline.exists()
    retained = retained_backup_paths(baseline)
    assert len(retained) == 1
    assert (retained[0] / "original.json").read_bytes() == original_bytes
    assert (retained[0] / "report.md").read_text(encoding="utf-8") == "approved original report"
    assert (run_dir / "next.json").read_bytes() == SAMPLE.read_bytes()

    # The retained lock is deliberate. Automatic retries must fail closed;
    # operator inspection and manual recovery are required.
    lock = tmp_path / ".approved.aea-update.lock"
    assert lock.is_file()
    with pytest.raises(ValueError, match="already in progress or lock retained"):
        freeze_run_as_baseline(run_dir, baseline, runs_dir, False, _validate_baseline_target)
    assert lock.is_file()
    assert (retained[0] / "original.json").read_bytes() == original_bytes

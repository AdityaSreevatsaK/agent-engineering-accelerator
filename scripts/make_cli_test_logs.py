"""Generate disposable CLI integration references from the current local calculator.

These are fresh synthetic test fixtures, NOT copies of unavailable fixed run
artifacts. Nothing is committed or overwritten, and no provider API is called.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log, write_eval_log
from inspect_ai.scorer import INCORRECT

ROOT = Path(__file__).resolve().parents[1]
CALCULATOR = ROOT / "examples" / "calculator" / "dataset.jsonl"
GOOD_AGENT = "examples.calculator.agent:build_agent"
INJECTED_FAILURES = frozenset({"subtract", "subtract_large"})


def make_cli_references(success: Path, defective: Path, temporary_root: Path) -> None:
    """Build a 10-case redacted baseline and inject exactly two artificial score failures."""
    for target in (success, defective):
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing to overwrite local test data: {target}")
    run_root = temporary_root / "calculator-cli-runs"
    env = {**os.environ}
    for name in (
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
        "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
    ):
        env[name] = ""
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    env["PYTHONUTF8"] = "1"
    command = [
        sys.executable, "-m", "agent_accelerator.cli", "run", str(CALCULATOR),
        "--agent", GOOD_AGENT, "--runs-dir", str(run_root), "--max-samples", "1",
    ]
    result = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=300, check=False,
    )
    if result.returncode != 0 or "passed=10/10" not in result.stdout:
        raise RuntimeError(
            "The synthetic calculator baseline did not complete cleanly: "
            f"exit={result.returncode}\nstdout={result.stdout[-1200:]}\nstderr={result.stderr[-1200:]}"
        )
    dirs = list(run_root.iterdir())
    if len(dirs) != 1 or not dirs[0].is_dir():
        raise AssertionError("Expected one disposable evaluation run")
    logs = list(dirs[0].glob("*.json"))
    if len(logs) != 1:
        raise AssertionError("Expected one Inspect log in the disposable run")
    original = read_eval_log(logs[0])
    if len(original.samples or []) != 10:
        raise AssertionError("Expected ten calculator cases in the baseline")
    if {str(s.id) for s in original.samples or [] if not s.scores["case_checks"].value == "C"}:
        raise AssertionError("Some baseline cases did not return the passing category")
    for sample in original.samples or []:
        if sample.input != "[REDACTED]" or sample.target != "[REDACTED]":
            raise AssertionError("Refusing to preserve an unredacted synthetic baseline")
    success.parent.mkdir(parents=True, exist_ok=True)
    defective.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(logs[0], success)

    broken = read_eval_log(logs[0])
    matched: set[str] = set()
    for sample in broken.samples or []:
        case_id = str(sample.id)
        if case_id in INJECTED_FAILURES:
            matched.add(case_id)
            sample.scores["case_checks"].value = INCORRECT
            sample.scores["case_checks"].explanation = "deliberate synthetic score regression"
    if matched != INJECTED_FAILURES:
        raise AssertionError(f"Could not inject all intended synthetic regressions: {matched}")
    write_eval_log(broken, location=defective)

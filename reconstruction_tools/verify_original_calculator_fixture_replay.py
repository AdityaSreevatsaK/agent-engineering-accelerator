"""Run original fixture-dependent compare tests using temporary source-replayed logs.

This is NEW replay validation, NOT restoration of historical captured JSON bytes.
The real video-recovered Strands calculator emits fresh Inspect logs locally; we
stage them only during pytest, remove both afterwards and never upload logs.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from inspect_ai.log import read_eval_log, write_eval_log

from agent_accelerator.compare import load_results
from reconstruction_tools.run_compare_without_original_fixtures import DEFERRED, preflight

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CAPTURE_PATH = FIXTURES / "calculator_capture_content.json"
BROKEN_PATH = FIXTURES / "calculator_broken_redacted.json"
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
    })
    result = subprocess.run(
        [sys.executable, *args], cwd=ROOT, env=env,
        text=True, capture_output=True, encoding="utf-8", errors="replace",
        timeout=300, check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"Offline command failed with exit {result.returncode}: {args[:4]}\n"
            f"stdout:\n{result.stdout[-5000:]}\nstderr:\n{result.stderr[-5000:]}"
        )
    return result


def one_log(runs: Path) -> Path:
    dirs = [path for path in runs.iterdir() if path.is_dir()]
    if len(dirs) != 1:
        raise AssertionError(f"Expected a single run directory, found {len(dirs)}")
    logs = list(dirs[0].glob("*.json"))
    if len(logs) != 1:
        raise AssertionError(f"Expected one local Inspect JSON, found {len(logs)}")
    return logs[0]


def main() -> None:
    preflight()
    if any(p.exists() for p in (CAPTURE_PATH, BROKEN_PATH)):
        raise RuntimeError(
            "Refusing to overwrite fixture paths: original data may have been provided; "
            "review the test deferrals and run them against originals instead"
        )
    if not (ROOT / "examples" / "calculator" / "rules.py").is_file():
        raise RuntimeError("Original video-recovered calculator rules.py not restored")
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aea-original-replay-") as workspace:
        temp = Path(workspace)
        try:
            for name, agent, captured, target in (
                ("normal", "build_agent", True, CAPTURE_PATH),
                ("broken", "build_broken_agent", False, BROKEN_PATH),
            ):
                run_dir = temp / name
                args = [
                    "-m", "agent_accelerator.cli", "run", str(DATASET),
                    "--agent", f"examples.calculator.agent:{agent}",
                    "--adapter", "strands", "--runs-dir", str(run_dir),
                    "--epochs", "1", "--max-samples", "1",
                ]
                if captured:
                    args.append("--capture-content")
                result = invoke(*args)
                expected = "passed=10/10" if captured else "passed=8/10"
                if expected not in result.stdout:
                    raise AssertionError(f"Source replay produced unexpected {name} outcome: {result.stdout[-2500:]}")
                source_log = one_log(run_dir)
                shutil.copyfile(source_log, target)
                if captured:
                    # The ORIGINAL October 12 capture predates the newer
                    # case_checks.tool_call_count summary field (confirmed
                    # by the video and recorded historical test contract).
                    # Reproduce that historical *log schema only* in this
                    # temporary source replay; do not alter the production
                    # scorer or pretend these are original fixture bytes.
                    log = read_eval_log(target)
                    for sample in log.samples or []:
                        for score in (sample.scores or {}).values():
                            if score.metadata:
                                score.metadata.pop("tool_call_count", None)
                    for reduction in log.reductions or []:
                        for score in reduction.samples:
                            if score.metadata:
                                score.metadata.pop("tool_call_count", None)
                    write_eval_log(log, location=target)
                parsed = load_results(target)
                if parsed.status != "success" or parsed.capture_content is not captured:
                    raise AssertionError(f"Invalid or mislabelled {name} replay log")

            # These paths are fresh source-generated temporary replacements,
            # NEVER asserted to be the original 12 October historical bytes.
            test_nodes = [f"{path}::{name}" for path, cases in DEFERRED.items() for name in cases]
            tests = invoke("-m", "pytest", "-q", "-o", "addopts=", *test_nodes)
            print(tests.stdout, end="", flush=True)
            if tests.stderr:
                print(tests.stderr, file=sys.stderr, end="", flush=True)
            match = re.search(r"\b(\d+) passed\b", tests.stdout)
            if not match or int(match.group(1)) < len(test_nodes):
                raise AssertionError("Source-replay unit suite did not exercise all original fixture-dependent tests")
            print(
                "SOURCE REPLAY ONLY: original fixture-dependent test functions passed "
                "using fresh video-recovered calculator logs, NOT historical JSON bytes",
                flush=True,
            )
        finally:
            # Use only these explicit known names; never delete other user files.
            for target in (CAPTURE_PATH, BROKEN_PATH):
                target.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

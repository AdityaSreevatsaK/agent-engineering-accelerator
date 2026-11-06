"""Run the video-recovered calculator through AEA using real Strands offline.

All inputs and logs live in a disposable folder. This verifies actual recovered
rules.py + agent.py + dataset.jsonl, not synthetic stand-ins or model APIs.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from agent_accelerator.compare import load_results

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"


def cli(*args: str, code: int = 0) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
    })
    proc = subprocess.run(
        [sys.executable, "-m", "agent_accelerator.cli", *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=240, check=False,
    )
    if proc.returncode != code:
        raise AssertionError(
            f"CLI {args[0]} exit {proc.returncode} expected {code}\n"
            f"stdout:\n{proc.stdout[-5000:]}\nstderr:\n{proc.stderr[-5000:]}"
        )
    return proc


def main() -> None:
    if not DATASET.is_file() or not (DATASET.parent / "rules.py").is_file():
        raise AssertionError("Historical calculator agent, dataset or rules not restored")
    with tempfile.TemporaryDirectory(prefix="aea-original-calculator-") as temporary:
        runs = Path(temporary) / "runs"
        common = (DATASET.as_posix(), "--adapter", "strands", "--runs-dir", str(runs), "--max-samples", "1")

        normal = cli("run", *common, "--agent", "examples.calculator.agent:build_agent")
        if "passed=10/10" not in normal.stdout:
            raise AssertionError(f"Recovered normal calculator failed:\n{normal.stdout[-5000:]}")
        [normal_dir] = sorted(p for p in runs.iterdir() if p.is_dir())
        baseline = load_results(normal_dir)
        if baseline.status != "success" or baseline.pass_rate != 1.0 or baseline.capture_content:
            raise AssertionError("Original calculator baseline is not a complete redacted 10/10 evaluation")

        broken = cli("run", *common, "--agent", "examples.calculator.agent:build_broken_agent")
        if "passed=8/10" not in broken.stdout:
            raise AssertionError(f"Broken calculator did not reproduce the seeded 8/10 regression:\n{broken.stdout[-5000:]}")
        broken_dir = next(p for p in runs.iterdir() if p.is_dir() and p != normal_dir)
        regressed = load_results(broken_dir)
        if regressed.status != "success" or regressed.pass_rate != 0.8:
            raise AssertionError("Broken model failed to preserve the expected 8/10 result")
        actual_failed = {name for name, case in regressed.cases.items() if not case.passed}
        if actual_failed != {"subtract", "subtract_large"}:
            raise AssertionError(f"Seeded subtraction regression differs from original: {actual_failed}")
        if regressed.dataset_sha256 != baseline.dataset_sha256:
            raise AssertionError("The normal and broken agent must use the same historic dataset")

        comparison = cli("compare", str(normal_dir), str(broken_dir), code=1)
        if not all(
            token in comparison.stdout
            for token in ("**REGRESSION**", "subtract", "subtract_large", "2 case(s) newly failing")
        ):
            raise AssertionError(f"Original calculator comparison missing regression evidence:\n{comparison.stdout[-5000:]}")

        flaky = cli(
            "run", *common, "--agent", "examples.calculator.agent:build_flaky_agent", "--epochs", "2"
        )
        if "passed=8/10" not in flaky.stdout:
            raise AssertionError(f"Seeded flaky calculator did not reproduce 8/10:\n{flaky.stdout[-5000:]}")
        flaky_dir = next(p for p in runs.iterdir() if p.is_dir() and p not in (normal_dir, broken_dir))
        unstable = load_results(flaky_dir)
        flaky_cases = {name for name, case in unstable.cases.items() if case.flaky}
        if flaky_cases != {"subtract", "subtract_large"}:
            raise AssertionError(f"Two original seeded flaky cases were not identified: {flaky_cases}")
        print("PASSED: recovered original calculator normal=10/10, broken=8/10, flaky=8/10 (2 epochs)")
        print("PASSED: normal/broken compare exit 1 and exactly two subtraction regressions")
        print("No cloud providers, user credentials, historical capture stand-ins or paid model calls")


if __name__ == "__main__":
    main()

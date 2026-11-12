"""Verify good-to-bad agent regression detection through the public AEA CLI."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
DATASET = "examples/orders/dataset.jsonl"
GOOD = "examples.orders.agent:build_agent"
BAD = "examples.orders.agent:build_broken_agent"


def command(target: str, baseline: Path, runs: Path, *, update: bool) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable, "-m", "agent_accelerator.cli",
        "check", DATASET,
        "--adapter", "strands", "--agent", target,
        "--baseline", str(baseline), "--runs-dir", str(runs),
        "--max-samples", "1",
    ]
    if update:
        argv.append("--update-baseline")
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "OPENAI_API_KEY": "",
        "AZURE_OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
    }
    return subprocess.run(
        argv, cwd=ROOT, env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        timeout=300, check=False,
    )


def require_success(name: str, result: subprocess.CompletedProcess[str], tally: str, verdict: str) -> None:
    if result.returncode != 0 or tally not in result.stdout or verdict not in result.stdout:
        raise AssertionError(
            f"{name}: expected exit=0, {tally}, {verdict}\n"
            f"exit={result.returncode}\n"
            f"stdout:\n{result.stdout[-3000:]}\n"
            f"stderr:\n{result.stderr[-2000:]}"
        )


def main() -> None:
    with TemporaryDirectory(prefix="aea-regression-gate-") as tmp:
        base = Path(tmp)
        baseline = base / "baseline"
        freeze = command(GOOD, baseline, base / "freeze-runs", update=True)
        require_success("freeze", freeze, "passed=11/11", "BASELINE frozen:")
        original = sorted(baseline.glob("*.json"))
        if len(original) != 1 or not (baseline / "report.md").is_file():
            raise AssertionError("Frozen baseline lacks one JSON log and its report")
        saved = {p.name: p.read_bytes() for p in baseline.iterdir() if p.is_file()}

        good = command(GOOD, baseline, base / "good-runs", update=False)
        require_success("matching run", good, "passed=11/11", "OK: baseline")
        if not list((base / "good-runs").rglob("comparison.md")):
            raise AssertionError("Matching check did not write a comparison")

        broken = command(BAD, baseline, base / "bad-runs", update=False)
        reports = list((base / "bad-runs").rglob("comparison.md"))
        if broken.returncode != 1 or "REGRESSION: baseline" not in broken.stdout or len(reports) != 1:
            raise AssertionError(
                f"Broken agent failed to trigger a proper regression\n"
                f"exit={broken.returncode}\nstdout:\n{broken.stdout[-3000:]}\n"
                f"stderr:\n{broken.stderr[-2000:]}"
            )
        comparison = reports[0].read_text(encoding="utf-8")
        if "## Newly failing" not in comparison or "refund" not in comparison.lower():
            raise AssertionError("Regression report did not identify the defective refund behaviour")

        after = {p.name: p.read_bytes() for p in baseline.iterdir() if p.is_file()}
        if after != saved:
            raise AssertionError("Checking a broken agent unexpectedly changed the approved baseline")
        print("PASS: full CLI good baseline, matching run and deliberately broken refund policy")
        print("PASS: regression exit=1, documented failing case and unchanged baseline")


if __name__ == "__main__":
    main()

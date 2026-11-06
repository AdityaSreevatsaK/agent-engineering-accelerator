"""Cross-platform, zero-provider end-to-end smoke for the recovered AEA CLI.

This uses AEA's *reconstructed starter* and its deterministic Strands model
double. No historical calculator examples, credentials or external models are
needed. The temporary demo is not a substitute for original AEA v2.2.0 files.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


AGENT = "demo_agent.agent:build_offline_agent"


def aea(workdir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    env["AWS_ACCESS_KEY_ID"] = ""
    env["AWS_SECRET_ACCESS_KEY"] = ""
    env["AWS_SESSION_TOKEN"] = ""
    env["INSPECT_LOG_DIR"] = str(workdir / "inspect-logs")
    result = subprocess.run(
        [sys.executable, "-m", "agent_accelerator.cli", *args],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"aea {args[0]} failed (exit {result.returncode})\n"
            f"stdout:\n{result.stdout[-6000:]}\n"
            f"stderr:\n{result.stderr[-6000:]}"
        )
    return result


def assert_five_cases(result: subprocess.CompletedProcess[str]) -> None:
    if "passed=5/5" not in result.stdout:
        raise AssertionError(
            "Offline starter did not pass all five declared evaluation cases.\n"
            f"stdout:\n{result.stdout[-6000:]}\n"
            f"stderr:\n{result.stderr[-6000:]}"
        )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aea-offline-e2e-") as directory:
        root = Path(directory)
        starter = root / "demo_agent"
        init = aea(root, "init", starter.name)
        if not (starter / "agent.py").is_file() or not (starter / "dataset.jsonl").is_file():
            raise AssertionError(f"Starter missing after init: {init.stdout}")
        dataset = "demo_agent/dataset.jsonl"
        common = (
            dataset, "--agent", AGENT, "--runs-dir", "runs", "--epochs", "1"
        )

        first = aea(
            root, "check", *common, "--baseline", "baseline", "--update-baseline"
        )
        assert_five_cases(first)
        baseline = root / "baseline"
        if not (baseline / "report.md").is_file():
            raise AssertionError("Offline baseline was not created with its report")

        second = aea(root, "check", *common, "--baseline", "baseline")
        assert_five_cases(second)
        runs = sorted(p for p in (root / "runs").iterdir() if p.is_dir())
        if len(runs) != 2:
            raise AssertionError(f"Expected two local evaluation runs, found {runs}")
        current = runs[-1]
        comparison = current / "comparison.md"
        if not comparison.is_file() or not comparison.read_text(encoding="utf-8").strip():
            raise AssertionError("Offline check did not create comparison.md")

        aea(root, "compare", str(baseline), str(current), "--output", "comparison-copy.md")
        if not (root / "comparison-copy.md").is_file():
            raise AssertionError("Standalone compare did not write its report")
        report = aea(root, "report", str(current))
        if not report.stdout.strip():
            raise AssertionError("Standalone report returned no content")

        aea(
            root, "export", str(current / "report.md"),
            "--format", "html", "--output", "offline-report.html",
        )
        html = root / "offline-report.html"
        if not html.is_file() or "<html" not in html.read_text(encoding="utf-8").casefold():
            raise AssertionError("Offline HTML export is absent or not HTML")
        print(
            "PASSED: offline Strands starter (5/5 cases twice), "
            "baseline freeze, regression check, compare, report and HTML export."
        )
        print("No cloud/model calls or historical fixtures; this is a synthetic integration smoke.")


if __name__ == "__main__":
    main()

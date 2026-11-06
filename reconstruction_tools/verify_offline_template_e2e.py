"""Cross-platform, zero-provider end-to-end smoke for the recovered AEA CLI.

This uses AEA's *reconstructed starter* and its deterministic Strands model
double. No historical calculator examples, credentials or external models are
needed. The temporary demo is not a substitute for original AEA v2.2.0 files.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path


AGENT = "demo_agent.agent:build_offline_agent"


def aea(workdir: Path, *args: str, expected_code: int = 0) -> subprocess.CompletedProcess[str]:
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
    if result.returncode != expected_code:
        raise AssertionError(
            f"aea {args[0]} returned {result.returncode}, expected {expected_code}\n"
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
        # The historical AEA CLI includes explicit regression thresholds. Exercise
        # their end-to-end nonzero-exit behaviour against a *real* offline run,
        # without changing the dataset or invoking a paid model/provider.
        before_hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in baseline.iterdir()
            if p.is_file()
        }
        agent_file = starter / "agent.py"
        original_agent = agent_file.read_text(encoding="utf-8")
        original_london = '"london": "09:00-17:30"'
        changed_london = '"london": "08:00-17:30"'
        if original_agent.count(original_london) != 1:
            raise AssertionError("Offline starter model changed: regression mutation is no longer safe")
        agent_file.write_text(
            original_agent.replace(original_london, changed_london, 1),
            encoding="utf-8",
        )

        broken = aea(root, "check", *common, "--baseline", "baseline", expected_code=1)
        if "passed=4/5" not in broken.stdout or "REGRESSION:" not in broken.stdout:
            raise AssertionError(
                "Modified offline agent did not produce one detected regression.\n"
                f"stdout:\n{broken.stdout[-6000:]}\nstderr:\n{broken.stderr[-6000:]}"
            )
        all_runs = sorted(p for p in (root / "runs").iterdir() if p.is_dir())
        if len(all_runs) != 3:
            raise AssertionError("Expected three offline evaluation runs including the regressed run")
        regressed = all_runs[-1]
        comparison_text = (regressed / "comparison.md").read_text(encoding="utf-8")
        if not all(
            phrase in comparison_text
            for phrase in ("**REGRESSION**", "## Newly failing", "exact_answer", "1 case(s) newly failing")
        ):
            raise AssertionError("Persisted comparison omitted regression verdict or failing case")
        standalone = aea(
            root, "compare", str(baseline), str(regressed),
            "--output", "detected-regression.md", expected_code=1,
        )
        if "**REGRESSION**" not in standalone.stdout:
            raise AssertionError("Standalone compare failed to return a regression verdict")
        saved = root / "detected-regression.md"
        if not saved.is_file() or saved.read_text(encoding="utf-8").strip() != standalone.stdout.strip():
            raise AssertionError("Standalone nonzero compare did not write the report")

        # Explicitly relax *both* applicable thresholds. No new evaluation
        # request is needed, and the same captured run can be compared again.
        allowed = aea(
            root, "compare", str(baseline), str(regressed),
            "--max-new-failures", "1", "--max-pass-rate-drop", "0.2",
        )
        if "**OK**" not in allowed.stdout or "## Newly failing" not in allowed.stdout:
            raise AssertionError("Allowed regression did not honour threshold policy")
        after_hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in baseline.iterdir()
            if p.is_file()
        }
        if before_hashes != after_hashes:
            raise AssertionError("Regression check unexpectedly modified frozen baseline files")

        print(
            "PASSED: offline Strands starter (5/5 twice), baseline freeze, "
            "check/compare/report/HTML export, and a detected 4/5 regression."
        )
        print(
            "PASSED: regression CLI exit code 1, persisted comparison, "
            "allowed threshold exit code 0, immutable baseline."
        )
        print("No cloud/model calls or historical fixtures; this is an offline integration smoke.")


if __name__ == "__main__":
    main()

"""Rehearse two AEA adapter integrations with synthetic cases and deliberately defective agents.

This is automated technical evidence, NOT evidence that two independent teams adopted
AEA. Choose a new output directory; no prior run or baseline is overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = "examples/calculator/dataset.jsonl"
SCENARIOS = (
    ("strands", "examples.calculator.agent"),
    ("langgraph", "examples.calculator.langgraph_agent"),
)
EMPTY_KEYS = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
)


def _run_cli(adapter: str, factory: str, baseline: Path, runs: Path, update: bool) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable, "-m", "agent_accelerator.cli",
        "check", DATASET, "--adapter", adapter, "--agent", factory,
        "--baseline", str(baseline), "--runs-dir", str(runs), "--max-samples", "1",
    ]
    if update:
        args.append("--update-baseline")
    env = {**os.environ, **{key: "" for key in EMPTY_KEYS}}
    env.update({"PYTHONUTF8": "1", "AWS_EC2_METADATA_DISABLED": "true"})
    return subprocess.run(
        args, cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )


def _require(stage: str, result: subprocess.CompletedProcess[str], code: int, *markers: str) -> None:
    if result.returncode != code or any(marker not in result.stdout for marker in markers):
        raise AssertionError(
            f"{stage} unexpected CLI result: exit={result.returncode} (wanted {code})\n"
            f"stdout:\n{result.stdout[-2000:]}\nstderr:\n{result.stderr[-2000:]}"
        )


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def _comparison_path(run_dir: Path) -> Path:
    matches = list(run_dir.rglob("comparison.md"))
    if len(matches) != 1:
        raise AssertionError(f"Expected one comparison in {run_dir}, found {len(matches)}")
    return matches[0]


def run_rehearsal(output: Path, repeats: int = 3) -> dict[str, object]:
    """Exercise real AEA CLI baseline and regression handling independently for both adapters."""
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing pilot output: {output}")
    output.mkdir(parents=True, exist_ok=False)
    evidence: dict[str, object] = {
        "classification": "synthetic local adapter rehearsal; not independent team adoption",
        "dataset": DATASET,
        "baseline_comparison_repeats": repeats,
        "capture_content": False,
        "live_providers": False,
        "adapters": {},
    }

    by_adapter: dict[str, object] = {}
    for adapter, module in SCENARIOS:
        directory = output / adapter
        baseline = directory / "baseline"
        good = f"{module}:build_agent"
        broken = f"{module}:build_broken_agent"
        freeze = _run_cli(adapter, good, baseline, directory / "runs" / "freeze", update=True)
        _require(f"{adapter} freeze", freeze, 0, "passed=10/10", "BASELINE frozen:")
        snapshot = _hash_tree(baseline)
        if not snapshot or len(list(baseline.glob("*.json"))) != 1 or "report.md" not in snapshot:
            raise AssertionError(f"{adapter}: baseline log or report missing")

        checks: list[str] = []
        for attempt in range(1, repeats + 1):
            matches = directory / "runs" / f"unchanged-{attempt}"
            good_run = _run_cli(adapter, good, baseline, matches, update=False)
            _require(f"{adapter} unchanged {attempt}", good_run, 0, "passed=10/10", "OK: baseline")
            comparison = _comparison_path(matches)
            if "**OK**" not in comparison.read_text(encoding="utf-8"):
                raise AssertionError(f"{adapter}: unchanged agent produced an unexpected verdict")
            checks.append(comparison.relative_to(output).as_posix())

        broken_dir = directory / "runs" / "deliberately-broken"
        defective = _run_cli(adapter, broken, baseline, broken_dir, update=False)
        _require(f"{adapter} defective", defective, 1, "REGRESSION: baseline")
        regression = _comparison_path(broken_dir)
        report = regression.read_text(encoding="utf-8")
        if "## Newly failing" not in report or "subtract" not in report:
            raise AssertionError(f"{adapter}: regression was not attributed to a known calculator fault")
        if _hash_tree(baseline) != snapshot:
            raise AssertionError(f"{adapter}: approved baseline changed after comparisons")

        by_adapter[adapter] = {
            "baseline": baseline.relative_to(output).as_posix(),
            "baseline_fingerprints": snapshot,
            "unchanged_checks_passed": repeats,
            "unchanged_comparisons": checks,
            "regression_detected": True,
            "regression_exit_code": 1,
            "regression_report": regression.relative_to(output).as_posix(),
            "baseline_unchanged": True,
        }
        print(f"PASS {adapter}: 10/10 baseline, {repeats} unchanged run(s), regression detected, baseline intact", flush=True)

    evidence["adapters"] = by_adapter
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# AEA synthetic two-adapter pilot rehearsal",
        "",
        "**Status:** Automated technical rehearsal only. No independent team has participated.",
        "",
        "| Adapter | Baseline | Unchanged reruns | Deliberate regression | Baseline integrity |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, details in by_adapter.items():
        lines.append(
            f"| {name} | 10/10 pass | {details['unchanged_checks_passed']}/{repeats} pass "
            f"| detected (exit 1) | unchanged |"
        )
    lines += [
        "",
        "## Local evidence",
        "",
        "- [Machine-readable details](evidence.json)",
        "- All generated data uses the synthetic calculator double, without cloud-provider calls.",
        "- Input/output and tool argument payloads are redacted by default. Case identifiers, paths and trace names remain.",
    ]
    for name, details in by_adapter.items():
        lines.append(f"- {name}: [regression comparison]({details['regression_report']})")
    lines += [
        "",
        "## What remains for genuine adoption",
        "",
        "Independent engineers from two delivery teams must integrate their own existing agents,",
        "measure real onboarding/case-authoring time, record issues, and obtain security approval.",
        "Do not report this rehearsal as a completed organisational pilot.",
    ]
    (output / "REHEARSAL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory; must not exist")
    parser.add_argument("--repeats", type=int, default=3, help="Number of unchanged reruns per adapter (default 3)")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    run_rehearsal(args.output_dir.absolute(), repeats=args.repeats)
    print("PASS: both adapter rehearsal workflows completed; see REHEARSAL.md")


if __name__ == "__main__":
    main()

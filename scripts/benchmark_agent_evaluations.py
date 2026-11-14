"""Measure local AEA CLI runtime and deterministic fault detection on two standalone apps.

This is a synthetic technical benchmark. It cannot measure staff productivity,
model-provider latency, cost, savings or third-party adoption.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_independent_integrations import (
    SCENARIOS,
    call_cli,
    comparison_path,
    fingerprints,
    require,
    validate_dataset,
)

# A representative known faulty case for each independent synthetic app.
FAULT_CASE = {"equipment-strands": "equipment-202", "vendor-langgraph": "vendor-303"}


def percentile_nearest_rank(values: list[float], quantile: float) -> float:
    """Return an observed duration; never infer an unsupported tail percentile."""
    if not values or not 0 < quantile <= 1 or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("percentile requires finite nonnegative observations and quantile in (0, 1]")
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * quantile) - 1]


def measure(app_dir: Path, factory: str, baseline: Path, runs: Path, *, update: bool):
    start_ns = time.perf_counter_ns()
    result = call_cli(app_dir, factory, baseline, runs, update)
    elapsed_s = (time.perf_counter_ns() - start_ns) / 1_000_000_000
    return result, elapsed_s


def benchmark(output: Path, repeats: int = 3) -> dict[str, object]:
    """Run independently checked CLI calls and save only synthetic summary metrics."""
    if repeats < 1 or repeats > 20:
        raise ValueError("repeats must be between 1 and 20")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite benchmark evidence: {output}")
    output.mkdir(parents=True, exist_ok=False)
    scenarios: dict[str, object] = {}
    for name, adapter, app_dir in SCENARIOS:
        expected_cases = validate_dataset(app_dir / "dataset.jsonl")
        baseline = output / name / "baseline"
        runs = output / name / "runs"

        frozen, freeze_s = measure(app_dir, "build_agent", baseline, runs / "freeze", update=True)
        require(f"{name}:freeze", frozen, 0, f"passed={expected_cases}/{expected_cases}", "BASELINE frozen:")
        initial = fingerprints(baseline)
        if len(list(baseline.glob("*.json"))) != 1 or "report.md" not in initial:
            raise AssertionError(f"{name}: incomplete baseline")

        unchanged_seconds: list[float] = []
        for attempt in range(1, repeats + 1):
            check_dir = runs / f"unchanged-{attempt}"
            result, elapsed_s = measure(app_dir, "build_agent", baseline, check_dir, update=False)
            require(f"{name}:unchanged-{attempt}", result, 0, f"passed={expected_cases}/{expected_cases}", "OK: baseline")
            report = comparison_path(check_dir).read_text(encoding="utf-8")
            if "**OK**" not in report:
                raise AssertionError(f"{name}: unchanged comparison was not OK")
            unchanged_seconds.append(elapsed_s)

        fault_dir = runs / "fault-injection"
        faulty, fault_s = measure(app_dir, "build_broken_agent", baseline, fault_dir, update=False)
        require(f"{name}:deliberate-fault", faulty, 1, "REGRESSION: baseline")
        report = comparison_path(fault_dir).read_text(encoding="utf-8")
        known_case = FAULT_CASE[name]
        if "## Newly failing" not in report or known_case not in report:
            raise AssertionError(f"{name}: expected known regression {known_case} not explained")
        if fingerprints(baseline) != initial:
            raise AssertionError(f"{name}: regression check modified the baseline")
        observed = {
            "adapter": adapter,
            "synthetic_cases": expected_cases,
            "first_baseline_freeze_s": round(freeze_s, 4),
            "unchanged_check_seconds": [round(s, 4) for s in unchanged_seconds],
            "unchanged_median_s": round(statistics.median(unchanged_seconds), 4),
            "unchanged_p95_nearest_rank_s": round(percentile_nearest_rank(unchanged_seconds, 0.95), 4),
            "deliberate_fault_check_s": round(fault_s, 4),
            "total_measured_cli_s": round(freeze_s + sum(unchanged_seconds) + fault_s, 4),
            "unchanged_checks_passed": repeats,
            "controlled_faults_detected": 1,
            "controlled_faults_injected": 1,
            "known_failing_case": known_case,
            "baseline_unchanged": True,
        }
        scenarios[name] = observed
        print(
            f"PASS {name}: {expected_cases} cases; {repeats}/{repeats} unchanged checks; "
            f"1/1 planted regression; median check {observed['unchanged_median_s']:.3f}s; baseline unchanged",
            flush=True,
        )

    evidence: dict[str, object] = {
        "classification": "synthetic runtime measurements; no human-productivity or paid-provider evidence",
        "method": "wall-clock from before to after separate public AEA CLI subprocess calls",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "repeats_per_app": repeats,
        "scenarios": scenarios,
        "human_effort_minutes": None,
        "manual_baseline_minutes": None,
        "estimated_time_saved_pct": None,
        "claimable_independent_team_adoption": False,
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# AEA: synthetic runtime and regression benchmark",
        "",
        "**Scope:** observed CLI subprocess wall time, not model speed, independent adoption or engineer time saved.",
        "",
        "| Independent app | Cases | Freeze (s) | Repeat check median (s) | Repeat check p95* (s) | Fault check (s) | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, row in scenarios.items():
        lines.append(
            f"| {name} | {row['synthetic_cases']} | {row['first_baseline_freeze_s']:.3f} "
            f"| {row['unchanged_median_s']:.3f} | {row['unchanged_p95_nearest_rank_s']:.3f} "
            f"| {row['deliberate_fault_check_s']:.3f} "
            f"| {row['unchanged_checks_passed']}/{repeats} clean; 1/1 planted fault detected |"
        )
    lines.extend([
        "",
        "*p95 uses the nearest observed rank. Very few repetitions make this a descriptive maximum, not a reliable tail-latency estimate.*",
        "",
        "Both applications preserved their frozen baseline bytes. Each invokes real framework logic via the public AEA CLI.",
        "Agents and datasets are synthetic, and CPU scheduling, disk caches, runner load and agent complexity vary.",
        "**Do not compare the two applications as equal workloads or claim a productivity percentage.**",
        "The workflow intentionally does not contact billable model providers.",
        "",
        "See [evidence.json](evidence.json) for per-run measurements and [benchmark protocol](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/blob/dev/docs/BENCHMARKING.md) for study design.",
    ])
    (output / "BENCHMARK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("PASS: summary in BENCHMARK.md and evidence.json (no productivity claim)", flush=True)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="New directory; if absent use a disposable directory")
    parser.add_argument("--repeats", type=int, default=3, help="Unchanged checks per application (1 to 20)")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats must be between 1 and 20")
    if args.output_dir is None:
        with TemporaryDirectory(prefix="aea-synthetic-benchmark-") as directory:
            benchmark(Path(directory) / "evidence", repeats=args.repeats)
    else:
        benchmark(args.output_dir.absolute(), repeats=args.repeats)


if __name__ == "__main__":
    main()

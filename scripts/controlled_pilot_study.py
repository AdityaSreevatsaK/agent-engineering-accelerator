"""Compare a minimal conventional QA control with AEA on identical synthetic cases.

Both methods execute the actual local Strands/LangGraph application factories.
This measures bounded subprocess wall time and controlled regression parity,
not authoring effort, human onboarding, product superiority or adoption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from scripts.benchmark_agent_evaluations import FAULT_CASE
from scripts.conventional_agent_checks import EVIDENCE_PREFIX
from scripts.validate_independent_integrations import (
    CREDENTIALS, ROOT, SCENARIOS, call_cli, comparison_path, fingerprints, require, validate_dataset,
)

CONTROL = ROOT / "scripts" / "conventional_agent_checks.py"


def call_control(app_dir: Path, framework: str, factory: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **{key: "" for key in CREDENTIALS}}
    env.update({"AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"})
    return subprocess.run(
        [sys.executable, str(CONTROL), "--framework", framework, "--factory", factory],
        cwd=app_dir, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300, check=False,
    )


def control_summary(result: subprocess.CompletedProcess[str], *, expected_code: int, count: int) -> dict[str, Any]:
    if result.returncode != expected_code:
        raise AssertionError(f"conventional control returned {result.returncode}; expected {expected_code}")
    lines = [line.removeprefix(EVIDENCE_PREFIX) for line in result.stdout.splitlines()
             if line.startswith(EVIDENCE_PREFIX)]
    if len(lines) != 1:
        raise AssertionError("conventional control did not return a single summary")
    summary = json.loads(lines[0])
    if summary["case_count"] != count or summary["passing_case_count"] + len(summary["failing_case_ids"]) != count:
        raise AssertionError("control case coverage does not match the fixed dataset")
    if summary["passed"] != (expected_code == 0):
        raise AssertionError("control exit and pass/fail summary disagree")
    if len(set(summary["failing_case_ids"])) != len(summary["failing_case_ids"]):
        raise AssertionError("control produced repeated failure IDs")
    return summary


def newly_failing_ids(report: str, known_ids: set[str]) -> set[str]:
    """Extract the case identifiers, not the scorer's potentially sensitive explanation."""
    section = report.split("## Newly failing\n\n", 1)
    if len(section) != 2:
        raise AssertionError("AEA regression report has no newly-failing case section")
    rows = section[1].split("\n## ", 1)[0].splitlines()
    found = {case_id for case_id in known_ids
             if any(row == f"- {case_id}" or row.startswith(f"- {case_id} (") for row in rows)}
    if not found:
        raise AssertionError("AEA regression report has no recognised failing case IDs")
    if sum(row.startswith("- ") for row in rows) != len(found):
        raise AssertionError("AEA regression report contains unknown or repeated failing cases")
    return found


def measure(operation):
    start = time.perf_counter_ns()
    result = operation()
    return result, (time.perf_counter_ns() - start) / 1_000_000_000


def pilot(output: Path, repeats: int = 3) -> dict[str, Any]:
    if not 1 <= repeats <= 10:
        raise ValueError("repeats must be between 1 and 10")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing pilot evidence: {output}")
    output.mkdir(parents=True, exist_ok=False)
    result: dict[str, Any] = {
        "classification": "self-authored synthetic workflow comparison; not independent adoption",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "repeats": repeats,
        "methods": ["AEA public CLI", "direct framework standard-library control"],
        "measurement": "separate subprocess wall time, including Python import and evaluation",
        "human_effort_minutes": None,
        "time_to_first_report_minutes": None,
        "staff_productivity_change_percent": None,
        "claimable_multi_team_adoption": False,
        "production_security_approved": False,
        "scenarios": {},
    }
    for name, framework, app_dir in SCENARIOS:
        count = validate_dataset(app_dir / "dataset.jsonl")
        ids = {json.loads(line)["id"] for line in (app_dir / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
        scenario_dir = output / name
        baseline = scenario_dir / "aea_baseline"
        runs = scenario_dir / "aea_runs"
        frozen, freeze_s = measure(lambda: call_cli(app_dir, "build_agent", baseline, runs / "freeze", True))
        require(f"{name}:baseline", frozen, 0, f"passed={count}/{count}", "BASELINE frozen:")
        original = fingerprints(baseline)
        if len(list(baseline.glob("*.json"))) != 1 or "report.md" not in original:
            raise AssertionError(f"{name}: incomplete approved baseline")

        timings: dict[str, list[float]] = {"aea": [], "control": []}
        for attempt in range(1, repeats + 1):
            # Alternate warm-cache/process order, never run both simultaneously.
            order = ("control", "aea") if attempt % 2 else ("aea", "control")
            for method in order:
                if method == "aea":
                    checked, seconds = measure(
                        lambda a=attempt: call_cli(app_dir, "build_agent", baseline, runs / f"aea-clean-{a}", False)
                    )
                    require(f"{name}:aea-clean-{attempt}", checked, 0, f"passed={count}/{count}", "OK: baseline")
                    if "**OK**" not in comparison_path(runs / f"aea-clean-{attempt}").read_text(encoding="utf-8"):
                        raise AssertionError("AEA unchanged comparison was not OK")
                else:
                    checked, seconds = measure(lambda: call_control(app_dir, framework, "build_agent"))
                    control_summary(checked, expected_code=0, count=count)
                timings[method].append(seconds)

        faulty_aea, aea_bad_s = measure(
            lambda: call_cli(app_dir, "build_broken_agent", baseline, runs / "aea-fault", False)
        )
        require(f"{name}:aea-fault", faulty_aea, 1, "REGRESSION: baseline")
        faulty_control, control_bad_s = measure(
            lambda: call_control(app_dir, framework, "build_broken_agent")
        )
        control = control_summary(faulty_control, expected_code=1, count=count)
        control_failures = set(control["failing_case_ids"])
        aea_failures = newly_failing_ids(
            comparison_path(runs / "aea-fault").read_text(encoding="utf-8"), ids
        )
        if FAULT_CASE[name] not in control_failures or aea_failures != control_failures:
            raise AssertionError(
                f"{name}: disagreement on controlled defect IDs between direct control and AEA"
            )
        if fingerprints(baseline) != original:
            raise AssertionError(f"{name}: AEA comparison changed frozen baseline")

        result["scenarios"][name] = {
            "framework": framework,
            "synthetic_case_count": count,
            "dataset_sha256": hashlib.sha256((app_dir / "dataset.jsonl").read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
            "aea_first_baseline_freeze_s": round(freeze_s, 4),
            "aea_unchanged_seconds": [round(x, 4) for x in timings["aea"]],
            "control_unchanged_seconds": [round(x, 4) for x in timings["control"]],
            "aea_unchanged_median_s": round(statistics.median(timings["aea"]), 4),
            "control_unchanged_median_s": round(statistics.median(timings["control"]), 4),
            "aea_fault_check_s": round(aea_bad_s, 4),
            "control_fault_check_s": round(control_bad_s, 4),
            "failing_case_ids": sorted(control_failures),
            "parity_of_detected_defects": True,
            "aea_baseline_unchanged": True,
            "successful_unchanged_runs_per_method": repeats,
        }
        print(f"PASS {name}: {count}/{count} clean in both methods; {len(control_failures)} "
              f"identical failing case(s); {repeats} checks per method; baseline preserved", flush=True)

    (output / "evidence.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    markdown = [
        "# AEA: self-authored synthetic conventional-control study",
        "",
        "**Not a human onboarding, adoption, cost or productivity study.**",
        "",
        "Both methods run the identical standalone local agent factories, input cases and deliberate policy defects.",
        "The conventional control uses native framework invocation and hand-authored standard-library assertions.",
        "AEA additionally writes reports, trace summaries and retained baseline artefacts. Neither approach includes",
        "the time to develop or maintain the evaluation tooling and neither calls billable model providers.",
        "",
        "| Application | Cases | AEA median check (s) | Control median check (s) | Failing IDs agree |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, row in result["scenarios"].items():
        markdown.append(f"| {name} | {row['synthetic_case_count']} | {row['aea_unchanged_median_s']:.3f} "
                        f"| {row['control_unchanged_median_s']:.3f} | Yes ({len(row['failing_case_ids'])} cases) |")
    markdown.extend([
        "",
        "These are descriptive subprocess wall times from different software stacks and reporting features.",
        "**Do not infer comparative developer productivity or framework speed from the values.**",
        "One AEA baseline was frozen per app; the direct control compares the same explicit golden-case expectations.",
        "The study alternates which workflow runs first, while keeping samples non-concurrent.",
        "No human effort observations, independent engineers, client data or security approval were recorded.",
        "Full local evaluation logs are stored under this output directory and must not be publicly uploaded.",
        "See evidence.json for run timings and exact synthetic failing case IDs.",
        "",
    ])
    (output / "STUDY.md").write_text("\n".join(markdown), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3, help="one to ten unchanged checks for each method")
    parser.add_argument("--output-dir", type=Path, help="new directory; defaults to temporary evidence")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("--repeats must be between 1 and 10")
    if args.output_dir is None:
        with TemporaryDirectory(prefix="aea-control-pilot-") as folder:
            pilot(Path(folder) / "evidence", repeats=args.repeats)
    else:
        pilot(args.output_dir.absolute(), repeats=args.repeats)


if __name__ == "__main__":
    main()

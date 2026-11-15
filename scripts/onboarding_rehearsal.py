"""Measure a scripted first-install AEA onboarding pathway on two synthetic applications.

This measures machine wall-clock time, not human attention, learning,
case-authoring, problem solving, independent adoption or developer savings.
It runs trusted local example modules and creates only synthetic local data.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from scripts.benchmark_agent_evaluations import FAULT_CASE
from scripts.conventional_agent_checks import EVIDENCE_PREFIX
from scripts.controlled_pilot_study import control_summary, newly_failing_ids
from scripts.validate_independent_integrations import (
    CREDENTIALS, ROOT, SCENARIOS, comparison_path, fingerprints, validate_dataset,
)

SUMMARY_NAME = "ONBOARDING_REHEARSAL.md"
EVIDENCE_NAME = "evidence.json"


def clean_environment() -> dict[str, str]:
    """Disable familiar paid-provider credentials and EC2 metadata queries."""
    return {
        **os.environ,
        **{key: "" for key in CREDENTIALS},
        "AWS_EC2_METADATA_DISABLED": "true",
        "PYTHONUTF8": "1",
    }


def measure_command(
    command: list[str], *, cwd: Path, env: dict[str, str], expected_code: int,
    markers: tuple[str, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], float]:
    start_ns = time.perf_counter_ns()
    process = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=360, check=False,
    )
    seconds = (time.perf_counter_ns() - start_ns) / 1_000_000_000
    if process.returncode != expected_code or any(token not in process.stdout for token in markers):
        # Never print an application's stdout/stderr, which could contain user data.
        raise AssertionError(
            f"onboarding command failed its expected contract: "
            f"exit={process.returncode}, expected={expected_code}, "
            f"missing_markers={[m for m in markers if m not in process.stdout]}"
        )
    return process, seconds


def environment_python(root: Path) -> Path:
    executable = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not executable.is_file():
        raise FileNotFoundError(f"Expected installed project environment at {executable}")
    return executable


def run_onboarding(
    output: Path, *, install: bool = True, python: Path | None = None, root: Path = ROOT,
) -> dict[str, Any]:
    """Rehearse documented steps. Refuse to write into a pre-existing destination."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite onboarding evidence: {output}")
    output.mkdir(parents=True, exist_ok=False)
    env = clean_environment()
    install_seconds: float | None = None
    if install:
        _, install_seconds = measure_command(
            [
                "uv", "sync", "--python", sys.executable, "--all-extras",
                "--group", "dev", "--locked",
            ],
            cwd=root, env=env, expected_code=0,
        )
        interpreter = environment_python(root)
    else:
        interpreter = Path(python or sys.executable)
    if not interpreter.is_file():
        raise FileNotFoundError(f"Python interpreter missing: {interpreter}")

    evidence: dict[str, Any] = {
        "classification": "script-driven synthetic onboarding rehearsal, no human participants",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "environment": "new GitHub runner venv, possibly warm uv package cache" if install else "pre-installed local environment",
        "shared_dependency_install_seconds": round(install_seconds, 4) if install_seconds is not None else None,
        "time_from_human_checkout_minutes": None,
        "human_case_authoring_minutes": None,
        "human_configuration_minutes": None,
        "human_troubleshooting_minutes": None,
        "human_report_interpretation_minutes": None,
        "human_first_valid_report_minutes": None,
        "developer_effort_saved_percent": None,
        "independent_pilot_teams": 0,
        "security_approval_obtained": False,
        "scenarios": {},
    }

    for name, framework, app_dir in SCENARIOS:
        count = validate_dataset(app_dir / "dataset.jsonl")
        expected_ids = {
            json.loads(line)["id"]
            for line in (app_dir / "dataset.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        work = output / name
        baseline = work / "baseline"
        runs = work / "evaluations"
        cli = [str(interpreter), "-m", "agent_accelerator.cli"]
        doctor, doctor_s = measure_command(
            [*cli, "doctor", "dataset.jsonl", "--config", "aea.toml"],
            cwd=app_dir, env=env, expected_code=0, markers=("PASS: preflight complete",),
        )
        # Doctor must not create any evaluation data before the first actual run.
        if runs.exists() or baseline.exists():
            raise AssertionError(f"{name}: preflight created evaluation artefacts")
        steps = [
            "--config", "aea.toml", "--baseline", str(baseline),
            "--runs-dir", str(runs / "freeze"), "--max-samples", "1",
        ]
        frozen, first_aea_s = measure_command(
            [*cli, "check", "dataset.jsonl", *steps, "--update-baseline"],
            cwd=app_dir, env=env, expected_code=0,
            markers=(f"passed={count}/{count}", "BASELINE frozen:"),
        )
        if not (baseline / "report.md").is_file() or len(list(baseline.glob("*.json"))) != 1:
            raise AssertionError(f"{name}: first evaluation failed to produce a complete report")
        original = fingerprints(baseline)
        checked, comparison_s = measure_command(
            [
                *cli, "check", "dataset.jsonl", "--config", "aea.toml",
                "--baseline", str(baseline), "--runs-dir", str(runs / "unchanged"),
                "--max-samples", "1",
            ],
            cwd=app_dir, env=env, expected_code=0,
            markers=(f"passed={count}/{count}", "OK: baseline"),
        )
        if "**OK**" not in comparison_path(runs / "unchanged").read_text(encoding="utf-8"):
            raise AssertionError(f"{name}: clean comparison report was not OK")
        broken, aea_fault_s = measure_command(
            [
                *cli, "check", "dataset.jsonl", "--config", "aea.toml",
                "--agent", "agent:build_broken_agent",
                "--baseline", str(baseline), "--runs-dir", str(runs / "fault"),
                "--max-samples", "1",
            ],
            cwd=app_dir, env=env, expected_code=1, markers=("REGRESSION: baseline",),
        )
        aea_failures = newly_failing_ids(
            comparison_path(runs / "fault").read_text(encoding="utf-8"), expected_ids,
        )
        conventional = [
            str(interpreter), str(root / "scripts" / "conventional_agent_checks.py"),
            "--framework", framework,
        ]
        baseline_control, first_control_s = measure_command(
            [*conventional, "--factory", "build_agent"],
            cwd=app_dir, env=env, expected_code=0, markers=(EVIDENCE_PREFIX,),
        )
        control_summary(baseline_control, expected_code=0, count=count)
        faulty_control, control_fault_s = measure_command(
            [*conventional, "--factory", "build_broken_agent"],
            cwd=app_dir, env=env, expected_code=1, markers=(EVIDENCE_PREFIX,),
        )
        control_failures = set(
            control_summary(faulty_control, expected_code=1, count=count)["failing_case_ids"]
        )
        if aea_failures != control_failures or FAULT_CASE[name] not in aea_failures:
            raise AssertionError(f"{name}: onboarding approaches disagreed on known regression case IDs")
        if fingerprints(baseline) != original:
            raise AssertionError(f"{name}: onboarding checks modified the frozen reference")

        evidence["scenarios"][name] = {
            "framework": framework,
            "synthetic_case_count": count,
            "doctor_preflight_seconds": round(doctor_s, 4),
            "aea_first_valid_report_seconds": round(first_aea_s, 4),
            "aea_preflight_plus_first_report_seconds": round(doctor_s + first_aea_s, 4),
            "aea_unchanged_comparison_seconds": round(comparison_s, 4),
            "aea_fault_diagnosis_seconds": round(aea_fault_s, 4),
            "conventional_first_complete_case_check_seconds": round(first_control_s, 4),
            "conventional_fault_check_seconds": round(control_fault_s, 4),
            "newly_failing_case_ids": sorted(aea_failures),
            "regression_parity": True,
            "baseline_integrity_verified": True,
            "all_normal_cases_passed": count,
        }
        print(
            f"PASS {name}: {count}/{count} cases; doctor + first report "
            f"{doctor_s + first_aea_s:.3f}s; direct check {first_control_s:.3f}s; "
            f"regression parity {len(aea_failures)} case(s)",
            flush=True,
        )

    (output / EVIDENCE_NAME).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    rows = [
        "# AEA: scripted onboarding timing rehearsal",
        "",
        "**This records machine execution only. No engineer independently onboarded,**",
        "**no human authoring time was measured and no developer time-saving claim is justified.**",
        "",
        "A new CI job checks out source and runs the pinned dependency sync in a previously",
        "unpopulated environment. The uv package cache may be warm, and checkout, uv bootstrap",
        "and reading documentation are excluded from measured installation time.",
        "",
        f"Shared dependency installation: {install_seconds:.3f} s." if install_seconds is not None
        else "Shared dependency installation: not measured (pre-installed interpreter).",
        "",
        "| Synthetic app | Cases | Doctor (s) | AEA first report (s) | Direct framework check (s) | Fault agreement |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, row in evidence["scenarios"].items():
        rows.append(
            f"| {name} | {row['synthetic_case_count']} | {row['doctor_preflight_seconds']:.3f} "
            f"| {row['aea_first_valid_report_seconds']:.3f} "
            f"| {row['conventional_first_complete_case_check_seconds']:.3f} "
            f"| {len(row['newly_failing_case_ids'])} identical failing cases |"
        )
    rows += [
        "",
        "The AEA-first report is a baseline freeze with a real Inspect report and log.",
        "The direct-framework result is a compact golden-case summary, not an equivalent",
        "rich report, baseline or trace. Their durations are **not** a like-for-like",
        "measure of framework overhead or engineer productivity.",
        "The same installed environment is shared, and AEA runs before the direct check.",
        "Subprocess startup, local caches and CI runner contention affect elapsed times.",
        "No secret-bearing output or raw evaluation logs are included in these two summary files.",
        "Local baseline and evaluation artefacts beneath this output directory are NOT public evidence.",
        "",
        "To measure actual developer effort, an authorised human must independently",
        "integrate a real agent and time setup, coding, case authoring, failures and interpretation",
        "against their team's existing quality-assurance method.",
        "",
    ]
    (output / SUMMARY_NAME).write_text("\n".join(rows), encoding="utf-8")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="new output directory; defaults to a disposable one")
    parser.add_argument("--skip-install", action="store_true", help="use active Python, measure only agent workflow")
    args = parser.parse_args()
    if args.output_dir:
        run_onboarding(args.output_dir.absolute(), install=not args.skip_install)
    else:
        with TemporaryDirectory(prefix="aea-onboarding-") as directory:
            run_onboarding(Path(directory) / "evidence", install=not args.skip_install)


if __name__ == "__main__":
    main()

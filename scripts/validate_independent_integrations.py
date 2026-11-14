"""Exercise AEA against two independent synthetic applications through its public CLI.

Unlike in-repo example checks, subprocesses run from each application's own
working directory and import only its local agent module and installed packages.
No provider credentials or billable calls. This is not third-party adoption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    ("equipment-strands", "strands", ROOT / "integrations" / "equipment_strands"),
    ("vendor-langgraph", "langgraph", ROOT / "integrations" / "vendor_langgraph"),
)
CREDENTIALS = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
)


def call_cli(
    app_dir: Path, factory: str, baseline: Path, runs: Path, update: bool
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable, "-m", "agent_accelerator.cli",
        "check", "dataset.jsonl", "--config", "aea.toml", "--agent", f"agent:{factory}",
        "--baseline", str(baseline), "--runs-dir", str(runs), "--max-samples", "1",
    ]
    if update:
        command.append("--update-baseline")
    env = {**os.environ, **{key: "" for key in CREDENTIALS}}
    env.update({"AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"})
    return subprocess.run(
        command, cwd=app_dir, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )


def require(stage: str, completed: subprocess.CompletedProcess[str], exit_code: int, *markers: str) -> None:
    if completed.returncode != exit_code or any(marker not in completed.stdout for marker in markers):
        raise AssertionError(
            f"{stage}: expected exit={exit_code} and {markers}, got {completed.returncode}.\n"
            f"stdout:\n{completed.stdout[-2500:]}\nstderr:\n{completed.stderr[-2500:]}"
        )


def fingerprints(root: Path) -> dict[str, str]:
    return {
        str(file.relative_to(root)).replace("\\", "/"): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(root.rglob("*")) if file.is_file()
    }


def comparison_path(directory: Path) -> Path:
    matched = list(directory.rglob("comparison.md"))
    if len(matched) != 1:
        raise AssertionError(f"{directory}: expected one comparison, got {len(matched)}")
    return matched[0]


def validate_dataset(path: Path) -> int:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 12:
        raise AssertionError(f"{path}: integration fixture must contain 12 synthetic cases")
    ids = [row["id"] for row in rows]
    if len(set(ids)) != 12 or not all(row.get("input") and row.get("expected_output") for row in rows):
        raise AssertionError(f"{path}: case IDs or expectations invalid")
    return len(rows)


def run_validation(output: Path, repeats: int = 1) -> dict[str, object]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to replace existing integration evidence: {output}")
    output.mkdir(parents=True, exist_ok=False)
    evidence: dict[str, object] = {
        "classification": "automated external-style synthetic integration, not independent team adoption",
        "calls_to_paid_providers": False,
        "applications": {},
    }
    for name, adapter, app_dir in SCENARIOS:
        count = validate_dataset(app_dir / "dataset.jsonl")
        scenario_dir = output / name
        baseline = scenario_dir / "baseline"
        runs = scenario_dir / "runs"
        frozen = call_cli(app_dir, "build_agent", baseline, runs / "freeze", True)
        require(f"{name} freeze", frozen, 0, f"passed={count}/{count}", "BASELINE frozen:")
        initial = fingerprints(baseline)
        if len(list(baseline.glob("*.json"))) != 1 or "report.md" not in initial:
            raise AssertionError(f"{name}: incomplete frozen baseline")
        for attempt in range(1, repeats + 1):
            same_dir = runs / f"unchanged-{attempt}"
            same = call_cli(app_dir, "build_agent", baseline, same_dir, False)
            require(f"{name} repeat {attempt}", same, 0, f"passed={count}/{count}", "OK: baseline")
            if "**OK**" not in comparison_path(same_dir).read_text(encoding="utf-8"):
                raise AssertionError(f"{name}: passing comparison did not render an OK verdict")
        broken_dir = runs / "fault-injection"
        broken = call_cli(app_dir, "build_broken_agent", baseline, broken_dir, False)
        require(f"{name} regression", broken, 1, "REGRESSION: baseline")
        report = comparison_path(broken_dir).read_text(encoding="utf-8")
        if "## Newly failing" not in report or not any(
            word in report for word in ("equipment-202", "vendor-303")
        ):
            raise AssertionError(f"{name}: no actionable new failing case in report")
        intact = fingerprints(baseline) == initial
        if not intact:
            raise AssertionError(f"{name}: checking changed approved baseline bytes")
        evidence["applications"][name] = {
            "framework": adapter,
            "case_count": count,
            "baseline_cases_passed": count,
            "unchanged_runs_passed": repeats,
            "deliberate_regression_detected": True,
            "baseline_unchanged": intact,
            "regression_report": str(comparison_path(broken_dir).relative_to(output)).replace("\\", "/"),
        }
        print(
            f"PASS {name}: {count}/{count} baseline; {repeats} unchanged run(s); "
            "regression exit 1; baseline unchanged", flush=True,
        )

    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("PASS two distinct application integrations via public AEA CLI", flush=True)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, help="Unused directory for evidence (default: disposable temporary directory)"
    )
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    if args.output_dir:
        run_validation(args.output_dir.absolute(), args.repeats)
    else:
        with TemporaryDirectory(prefix="aea-independent-integrations-") as directory:
            run_validation(Path(directory) / "evidence", args.repeats)


if __name__ == "__main__":
    main()

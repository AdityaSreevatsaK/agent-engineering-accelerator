"""Verify recovered calculator, triage and expense examples with disposable baselines.

This is NEW functional verification, not a transcription of original AEA
baselines. The original baseline files are unavailable; no generated log is
copied to baselines/ or tests/fixtures/. Everything is deleted on completion.

The CLI is exercised in separate processes because the trace provider is
process-wide. Deterministic local agent doubles only, no paid model calls.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from inspect_ai.log import read_eval_log

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import dataset_sha256, load_dataset

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Scenario:
    name: str
    count: int
    good: str
    mutated: str
    failing: frozenset[str]
    flags: tuple[str, ...]


SCENARIOS = {
    "calculator": Scenario(
        "calculator", 10, "examples.calculator.agent:build_agent",
        "examples.calculator.agent:build_broken_agent",
        frozenset({"subtract", "subtract_large"}), ("--adapter", "strands"),
    ),
    "triage": Scenario(
        "triage", 12, "examples.triage.agent:build_agent",
        "examples.triage.agent:build_reworded_agent",
        frozenset({"charged_twice_furious", "angry_invoice_dispute"}),
        ("--config", "examples/triage/aea.toml"),
    ),
    "expense": Scenario(
        "expense", 12, "examples.expense.agent:build_agent",
        "examples.expense.agent:build_condensed_agent",
        frozenset({"receipt_missing_over_75", "receipt_missing_after_conversion", "reject_no_receipt"}),
        (
            "--config", "examples/expense/aea.toml",
            "--scorer", "examples.expense.scorers:amounts_grounded",
        ),
    ),
}


def invoke(args: list[str], *, exit_code: int) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "PYTHONUTF8": "1",
    }
    result = subprocess.run(
        [sys.executable, "-m", "agent_accelerator.cli", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300, check=False,
    )
    if result.returncode != exit_code:
        raise AssertionError(
            f"aea {args[0]} returned {result.returncode}, expected {exit_code}\n"
            f"stdout:\n{result.stdout[-4500:]}\nstderr:\n{result.stderr[-4500:]}"
        )
    return result


def file_digests(folder: Path) -> dict[str, str]:
    return {
        item.relative_to(folder).as_posix(): sha256(item.read_bytes()).hexdigest()
        for item in folder.rglob("*") if item.is_file()
    }


def assert_redacted_baseline(folder: Path, scenario: Scenario) -> None:
    results = load_results(folder)
    source = ROOT / "examples" / scenario.name / "dataset.jsonl"
    ids = {case.id for case in load_dataset(source)}
    if (
        len(ids) != scenario.count
        or set(results.cases) != ids
        or results.status != "success"
        or results.capture_content
        or results.dataset_sha256 != dataset_sha256(source)
        or any(not item.passed or item.error for item in results.cases.values())
    ):
        raise AssertionError(f"{scenario.name}: generated baseline result does not match dataset and 100% pass")
    log = read_eval_log(results.log_path)
    samples = log.samples or []
    if len(samples) != scenario.count:
        raise AssertionError(f"{scenario.name}: baseline sample count is incorrect")
    for sample in samples:
        if (
            sample.input != "[REDACTED]"
            or sample.target != "[REDACTED]"
            or sample.messages != []
            or sample.output is None
            or sample.output.completion != ""
        ):
            raise AssertionError(f"{scenario.name}/{sample.id}: default baseline contains unsanitised content")
    if not (folder / "report.md").is_file():
        raise AssertionError(f"{scenario.name}: baseline Markdown report missing")


def verify(scenario: Scenario, scratch: Path) -> None:
    dataset = ROOT / "examples" / scenario.name / "dataset.jsonl"
    if not dataset.is_file():
        raise AssertionError(f"{scenario.name}: recorded example dataset is missing")
    baseline = scratch / scenario.name / "GENERATED_NOT_HISTORICAL_baseline"
    runs = scratch / scenario.name / "GENERATED_NOT_HISTORICAL_runs"
    common = [
        "check", str(dataset), *scenario.flags,
        "--runs-dir", str(runs), "--baseline", str(baseline),
        "--max-samples", "1",
    ]
    freeze = invoke([*common, "--agent", scenario.good, "--update-baseline"], exit_code=0)
    if f"passed={scenario.count}/{scenario.count}" not in freeze.stdout or "BASELINE frozen:" not in freeze.stdout:
        raise AssertionError(f"{scenario.name}: baseline freeze did not report complete success")
    assert_redacted_baseline(baseline, scenario)
    before = file_digests(baseline)

    unchanged = invoke([*common, "--agent", scenario.good], exit_code=0)
    if "OK: baseline" not in unchanged.stdout:
        raise AssertionError(f"{scenario.name}: unchanged agent was not accepted")

    changed = invoke([*common, "--agent", scenario.mutated], exit_code=1)
    if "REGRESSION: baseline" not in changed.stdout:
        raise AssertionError(f"{scenario.name}: planted regression was not reported")
    run_dirs = [path for path in runs.iterdir() if path.is_dir()]
    if len(run_dirs) != 3:
        raise AssertionError(f"{scenario.name}: expected 3 CLI check run directories, got {len(run_dirs)}")
    mutated_dirs = []
    for path in run_dirs:
        results = load_results(path)
        failed = {name for name, case in results.cases.items() if not case.passed}
        if failed:
            mutated_dirs.append((path, results, failed))
    if len(mutated_dirs) != 1:
        raise AssertionError(f"{scenario.name}: expected precisely one mutated evaluation")
    regressed_dir, results, failed = mutated_dirs[0]
    if failed != scenario.failing or len(results.cases) != scenario.count:
        raise AssertionError(
            f"{scenario.name}: expected regressions {sorted(scenario.failing)}, found {sorted(failed)}"
        )
    if results.capture_content or results.dataset_sha256 != load_results(baseline).dataset_sha256:
        raise AssertionError(f"{scenario.name}: mutant changed dataset or retained capture content")
    comparison = regressed_dir / "comparison.md"
    if not comparison.is_file():
        raise AssertionError(f"{scenario.name}: missing persisted regression comparison")
    text = comparison.read_text(encoding="utf-8")
    if "**REGRESSION**" not in text or any(name not in text for name in scenario.failing):
        raise AssertionError(f"{scenario.name}: comparison omitted the planted regression details")
    if file_digests(baseline) != before:
        raise AssertionError(f"{scenario.name}: comparing a mutant modified the frozen baseline")
    print(
        f"PASS {scenario.name}: disposable redacted baseline {scenario.count}/{scenario.count}, "
        f"same-agent OK, seeded mutant {len(failed)} regressions, baseline immutable",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="all")
    selected = parser.parse_args(argv).scenario
    names = tuple(SCENARIOS) if selected == "all" else (selected,)
    with TemporaryDirectory(prefix="aea-baseline-functional-NOT-HISTORICAL-") as td:
        for name in names:
            verify(SCENARIOS[name], Path(td))
    print(
        "All generated baselines deleted. Historical originals remain missing and "
        "their byte fidelity is not established.",
        flush=True,
    )


if __name__ == "__main__":
    main()

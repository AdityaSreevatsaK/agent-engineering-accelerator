"""Replay all seven historical scripts/ci.sh example lanes without original baselines.

This is a reconstructed-code behavioural verification, NOT historical source
or baseline recovery. Every generated Inspect JSON, trace and Markdown output
is created under TemporaryDirectory and deleted when the process ends.
Original case files, source modules, manifest, baselines/ and master are never
modified. Only explicit offline deterministic model factories may execute.

Unlike isolated good-agent smokes, each of the seven lanes runs its actual
historical agent/adapter/options, compares two independent good runs, and
compares a seeded regression from the same original dataset. This preserves
the known ORIGINAL orders dataset-vs-rules wording conflict as a baseline
failure instead of silently editing either historical file.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory

from inspect_ai.log import read_eval_log

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import dataset_sha256, load_dataset

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Lane:
    label: str
    historical_baseline: str
    dataset: str
    adapter: str
    good: str
    mutant: str
    cases: int
    known_original_failures: frozenset[str]
    new_mutant_failures: frozenset[str]
    extra: tuple[str, ...] = ()


LANES = (
    Lane(
        "calculator-strands", "baselines/calculator.json",
        "examples/calculator/dataset.jsonl", "strands",
        "examples.calculator.agent:build_agent",
        "examples.calculator.agent:build_broken_agent",
        10, frozenset(), frozenset({"subtract", "subtract_large"}),
    ),
    Lane(
        "calculator-langgraph", "baselines/calculator.json",
        "examples/calculator/dataset.jsonl", "langgraph",
        "examples.calculator.langgraph_agent:build_agent",
        "examples.calculator.langgraph_agent:build_broken_agent",
        10, frozenset(), frozenset({"subtract", "subtract_large"}),
    ),
    Lane(
        "orders-strands", "baselines/orders.json",
        "examples/orders/dataset.jsonl", "strands",
        "examples.orders.agent:build_agent",
        "examples.orders.agent:build_broken_agent",
        11, frozenset({"total_spend"}),
        frozenset({"refund_not_delivered", "refund_outside_window"}),
    ),
    Lane(
        "expense-langgraph", "baselines/expense",
        "examples/expense/dataset.jsonl", "langgraph",
        "examples.expense.agent:build_agent",
        "examples.expense.agent:build_condensed_agent",
        12, frozenset(),
        frozenset({"receipt_missing_over_75", "receipt_missing_after_conversion", "reject_no_receipt"}),
        ("--scorer", "examples.expense.scorers:amounts_grounded"),
    ),
    Lane(
        "triage-langgraph", "baselines/triage",
        "examples/triage/dataset.jsonl", "langgraph",
        "examples.triage.agent:build_agent",
        "examples.triage.agent:build_reworded_agent",
        12, frozenset(),
        frozenset({"charged_twice_furious", "angry_invoice_dispute"}),
        (
            "--input-map", "examples.triage.agent:to_input",
            "--output-map", "examples.triage.agent:from_output",
        ),
    ),
    Lane(
        "policy_rag-langgraph", "baselines/policy_rag",
        "examples/policy_rag/dataset.jsonl", "langgraph",
        "examples.policy_rag.agent:build_agent",
        "examples.policy_rag.agent:build_confident_agent",
        11, frozenset(),
        frozenset({"hotel_cap_tier1_city", "hotel_cap_other_city"}),
    ),
    Lane(
        "helpdesk-langgraph", "baselines/helpdesk",
        "examples/helpdesk/dataset.jsonl", "langgraph",
        "examples.helpdesk.agent:build_agent",
        "examples.helpdesk.agent:build_ungated_agent",
        10, frozenset(),
        frozenset({"admin_local_docker", "admin_driver_update"}),
    ),
)
BY_LABEL = {lane.label: lane for lane in LANES}


def historical_invocations(root: Path = ROOT) -> dict[str, tuple[str, ...]]:
    """Read original recorded script, without executing uv or Bash."""
    source = (root / "scripts" / "ci.sh").read_text(encoding="utf-8")
    # The recorded script uses backslash-newline for the expense and triage
    # option lists. Parse literal invocations only, not the function body.
    unfolded = source.replace("\\\r\n", " ").replace("\\\n", " ")
    entries: dict[str, tuple[str, ...]] = {}
    for line in unfolded.splitlines():
        if not line.startswith("check "):
            continue
        argv = tuple(shlex.split(line))
        if len(argv) < 6 or argv[0] != "check":
            raise AssertionError(f"Unexpected historical check call: {line}")
        label = argv[1]
        if label in entries:
            raise AssertionError(f"Duplicate original CI example lane: {label}")
        entries[label] = argv[2:]
    if not entries:
        raise AssertionError("Historical scripts/ci.sh example checks absent")
    return entries


def verify_script_contract(root: Path = ROOT) -> None:
    """Refuse to pass if a source-recorded original CI example is skipped."""
    originals = historical_invocations(root)
    if set(originals) != set(BY_LABEL):
        raise AssertionError(
            "Historical seven-lane example CI manifest drift: "
            f"missing={sorted(set(originals) - set(BY_LABEL))}, "
            f"extra={sorted(set(BY_LABEL) - set(originals))}"
        )
    for lane in LANES:
        expected = (
            lane.historical_baseline, lane.dataset, lane.adapter, lane.good, *lane.extra,
        )
        if originals[lane.label] != expected:
            raise AssertionError(
                f"{lane.label}: reconstructed replay options do not match scripts/ci.sh "
                f"(historical={originals[lane.label]!r}, replay={expected!r})"
            )
        if not (root / lane.dataset).is_file():
            raise AssertionError(f"{lane.label}: original video-recovered dataset missing")


def run_command(args: list[str], expected: int) -> subprocess.CompletedProcess[str]:
    # Only deterministic original example factories from LANES are invoked.
    # Credentials unset even if a user's checkout contains provider settings.
    env = {
        **os.environ,
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "AZURE_OPENAI_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "PYTHONUTF8": "1",
    }
    completed = subprocess.run(
        [sys.executable, "-m", "agent_accelerator.cli", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300, check=False,
    )
    if completed.returncode != expected:
        raise AssertionError(
            f"{args[0]}: exit {completed.returncode}, expected {expected}\n"
            f"command={args!r}\nstdout={completed.stdout[-3500:]}\nstderr={completed.stderr[-4500:]}"
        )
    return completed


def single_run(lane: Lane, root: Path, factory: str, folder: str, expected_failures: frozenset[str]) -> Path:
    output = root / lane.label / folder
    if output.exists():
        raise AssertionError(f"{lane.label}: refuse to reuse generated test location {output}")
    flags = [
        "run", lane.dataset, "--adapter", lane.adapter,
        "--agent", factory, *lane.extra,
        "--runs-dir", str(output), "--max-samples", "1",
    ]
    execution = run_command(flags, expected=0)
    entries = [p for p in output.iterdir() if p.is_dir()]
    if len(entries) != 1:
        raise AssertionError(f"{lane.label}: expected a single run, found {entries}")
    run_dir = entries[0]
    result = load_results(run_dir)
    case_ids = {case.id for case in load_dataset(ROOT / lane.dataset)}
    failed = frozenset(k for k, value in result.cases.items() if not value.passed)
    expected_pass = lane.cases - len(expected_failures)
    if (
        result.status != "success" or result.capture_content
        or len(case_ids) != lane.cases or set(result.cases) != case_ids
        or result.dataset_sha256 != dataset_sha256(ROOT / lane.dataset)
        or failed != expected_failures
        or f"passed={expected_pass}/{lane.cases}" not in execution.stdout
    ):
        raise AssertionError(
            f"{lane.label}/{folder}: unexpected result: status={result.status}, "
            f"capture={result.capture_content}, failed={sorted(failed)}, "
            f"expected={sorted(expected_failures)}; stdout={execution.stdout[-3000:]}"
        )
    log = read_eval_log(result.log_path)
    samples = log.samples or []
    if len(samples) != lane.cases or any(
        sample.input != "[REDACTED]" or sample.target != "[REDACTED]"
        or sample.messages != [] or sample.output is None or sample.output.completion != ""
        for sample in samples
    ):
        raise AssertionError(f"{lane.label}/{folder}: Inspect log was not fully scrubbed")
    if not (run_dir / "report.md").is_file() or not (run_dir / "traces.jsonl").is_file():
        raise AssertionError(f"{lane.label}/{folder}: run lacks report or trace")
    return run_dir


def digests(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in folder.rglob("*") if p.is_file()
    }


def compare_runs(lane: Lane, baseline: Path, current: Path, output: Path,
                 expected_regression: bool) -> None:
    completed = run_command(
        ["compare", str(baseline), str(current), "--output", str(output)],
        expected=1 if expected_regression else 0,
    )
    rendered = output.read_text(encoding="utf-8")
    expected_verdict = "**REGRESSION**" if expected_regression else "**OK**"
    if expected_verdict not in completed.stdout or rendered.strip() != completed.stdout.strip():
        raise AssertionError(f"{lane.label}: compare stdout/file mismatch or missing {expected_verdict}")
    if expected_regression:
        missing = [name for name in lane.new_mutant_failures if name not in rendered]
        if missing:
            raise AssertionError(f"{lane.label}: missing newly failing IDs: {missing}")


def verify_lane(lane: Lane, root: Path) -> None:
    good = single_run(lane, root, lane.good, "source_good_baseline_NOT_HISTORICAL",
                      lane.known_original_failures)
    original_digest = digests(good)
    repeat = single_run(lane, root, lane.good, "source_good_repeat_NOT_HISTORICAL",
                        lane.known_original_failures)
    compare_runs(lane, good, repeat, root / f"{lane.label}_repeat.md", expected_regression=False)
    mutated = single_run(
        lane, root, lane.mutant, "mutant_NOT_HISTORICAL",
        lane.known_original_failures | lane.new_mutant_failures,
    )
    compare_runs(lane, good, mutated, root / f"{lane.label}_mutant.md", expected_regression=True)
    if digests(good) != original_digest:
        raise AssertionError(f"{lane.label}: baseline changed during comparison")
    print(
        f"PASS {lane.label}: {lane.cases} historical cases, "
        f"{len(lane.known_original_failures)} known original source conflict(s), "
        f"{len(lane.new_mutant_failures)} detected seeded regressions; "
        "independent good repeat OK and redacted baseline immutable",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=(*BY_LABEL, "all"), default="all")
    choice = parser.parse_args(argv).scenario
    verify_script_contract()
    selected = LANES if choice == "all" else (BY_LABEL[choice],)
    with TemporaryDirectory(prefix="aea-original-ci-SEVEN-LANES-NOT-HISTORICAL-") as folder:
        root = Path(folder)
        for lane in selected:
            verify_lane(lane, root)
    print(
        f"PASS: {len(selected)} recovered scripts/ci.sh examples, "
        f"{3 * len(selected)} native AEA runs and {2 * len(selected)} baseline comparisons. "
        "All generated baseline/log/trace artefacts deleted. "
        "Historical baselines and original locked CI remain unrecovered.",
        flush=True,
    )


if __name__ == "__main__":
    main()

"""Regression-test LangGraph default redaction and explicit opt-in capture.

The existing Strands starter E2E covers the same privacy boundary for Strands.
This *new* supplement covers two materially different reconstructed LangGraph
paths: triage's custom state maps and helpdesk's approval-gate interrupt.

Cases are derived from video-recovered examples with an added synthetic marker,
not historical original data. Temporary captured logs are never committed.
Do not construct live-agent factories or issue paid/cloud provider calls.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import load_dataset

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "AEA_SYNTHETIC_PRIVATE_PROBE_f721e18db0"
SCENARIOS: dict[str, tuple[str, tuple[str, ...]]] = {
    "triage": (
        "invoice_paid_status",
        ("--config", "examples/triage/aea.toml"),
    ),
    "helpdesk_interrupt": (
        "admin_local_docker",
        ("--adapter", "langgraph", "--agent", "examples.helpdesk.agent:build_agent"),
    ),
}
SOURCE = {
    "triage": "examples/triage/dataset.jsonl",
    "helpdesk_interrupt": "examples/helpdesk/dataset.jsonl",
}


def run_cli(dataset: Path, runs: Path, options: tuple[str, ...], *, capture: bool) -> Path:
    if runs.exists():
        raise AssertionError(f"Refusing to reuse output folder: {runs}")
    env = {
        **os.environ,
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "PYTHONUTF8": "1",
        "INSPECT_LOG_DIR": str(runs.parent / "inspect-internal"),
    }
    args = [
        sys.executable, "-m", "agent_accelerator.cli", "run", str(dataset),
        *options, "--runs-dir", str(runs), "--max-samples", "1",
    ]
    if capture:
        args.append("--capture-content")
    result = subprocess.run(
        args, cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )
    if result.returncode != 0 or "passed=1/1" not in result.stdout:
        raise AssertionError(
            f"LangGraph {options} capture={capture}: run failed "
            f"(exit={result.returncode})\nstdout={result.stdout[-3500:]}\n"
            f"stderr={result.stderr[-3500:]}"
        )
    if not runs.is_dir():
        raise AssertionError(f"No CLI runs directory: {runs}")
    found = [entry for entry in runs.iterdir() if entry.is_dir()]
    if len(found) != 1:
        raise AssertionError(f"Expected one run, got {found}")
    return found[0]


def marker_files(directory: Path) -> list[str]:
    """Look only inside generated run artefacts, never the intentionally marked input dataset."""
    return [
        file.relative_to(directory).as_posix()
        for file in directory.rglob("*")
        if file.is_file() and SENTINEL.encode("utf-8") in file.read_bytes()
    ]


def verify(name: str, scratch: Path) -> None:
    case_id, flags = SCENARIOS[name]
    original = ROOT / SOURCE[name]
    cases = [case for case in load_dataset(original) if case.id == case_id]
    if len(cases) != 1:
        raise AssertionError(f"Original example case {name}/{case_id} is missing")
    case = json.loads(cases[0].model_dump_json())
    case["input"] += " " + SENTINEL
    input_path = scratch / f"PROBE_DERIVED_NOT_HISTORICAL_{name}.jsonl"
    input_path.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")

    default_dir = run_cli(input_path, scratch / f"{name}_default", flags, capture=False)
    redacted = load_results(default_dir)
    if (
        redacted.capture_content
        or redacted.status != "success"
        or set(redacted.cases) != {case_id}
        or not redacted.cases[case_id].passed
    ):
        raise AssertionError(f"{name}: default LangGraph run was not a successful redacted 1/1")
    saved = marker_files(default_dir)
    if saved:
        raise AssertionError(f"{name}: private prompt persisted in default run artefacts: {saved}")
    if not (default_dir / "traces.jsonl").is_file() or not (default_dir / "report.md").is_file():
        raise AssertionError(f"{name}: tracing or reporting artefacts absent")

    captured_dir = run_cli(input_path, scratch / f"{name}_captured", flags, capture=True)
    captured = load_results(captured_dir)
    if (
        not captured.capture_content
        or captured.status != "success"
        or set(captured.cases) != {case_id}
        or not captured.cases[case_id].passed
        or captured.dataset_sha256 != redacted.dataset_sha256
    ):
        raise AssertionError(f"{name}: opt-in captured result status, IDs or dataset differ")
    if not marker_files(captured_dir):
        raise AssertionError(f"{name}: --capture-content did not retain synthetic probe input")
    if marker_files(default_dir):
        raise AssertionError(f"{name}: later opt-in capture contaminated earlier redacted files")

    print(
        f"PASS {name}: original derived case {case_id}, "
        "default output contains no synthetic prompt; explicit capture retains it",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="all")
    requested = parser.parse_args(argv).scenario
    selected = tuple(SCENARIOS) if requested == "all" else (requested,)
    with TemporaryDirectory(prefix="aea-langgraph-PRIVACY-PROBE-NOT-HISTORICAL-") as folder:
        root = Path(folder)
        for scenario in selected:
            verify(scenario, root)
    print(
        "PASS: all synthetic opt-in logs deleted and no historical evidence replaced. "
        "This tests sample payload redaction, not safety of arbitrary custom agents/scorers.",
        flush=True,
    )


if __name__ == "__main__":
    main()

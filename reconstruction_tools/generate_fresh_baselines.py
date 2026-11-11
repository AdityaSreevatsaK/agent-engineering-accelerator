"""Generate *new*, scrubbed AEA example baselines beside (never over) the originals.

Usage:
    python -m reconstruction_tools.generate_fresh_baselines --dry-run
    python -m reconstruction_tools.generate_fresh_baselines

Uses the reconstructed AEA CLI to execute the real offline model doubles.
No historical file restoration or original-byte fidelity is claimed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "baselines-new"


@dataclass(frozen=True)
class Baseline:
    name: str
    dataset: str
    adapter: str
    agent: str
    flags: tuple[str, ...] = ()


BASELINES = (
    Baseline("calculator-strands", "examples/calculator/dataset.jsonl",
             "strands", "examples.calculator.agent:build_agent"),
    Baseline("calculator-langgraph", "examples/calculator/dataset.jsonl",
             "langgraph", "examples.calculator.langgraph_agent:build_agent"),
    Baseline("orders", "examples/orders/dataset.jsonl",
             "strands", "examples.orders.agent:build_agent"),
    Baseline("expense", "examples/expense/dataset.jsonl",
             "langgraph", "examples.expense.agent:build_agent",
             ("--scorer", "examples.expense.scorers:amounts_grounded")),
    Baseline("triage", "examples/triage/dataset.jsonl",
             "langgraph", "examples.triage.agent:build_agent",
             ("--input-map", "examples.triage.agent:to_input",
              "--output-map", "examples.triage.agent:from_output")),
    Baseline("policy_rag", "examples/policy_rag/dataset.jsonl",
             "langgraph", "examples.policy_rag.agent:build_agent"),
    Baseline("helpdesk", "examples/helpdesk/dataset.jsonl",
             "langgraph", "examples.helpdesk.agent:build_agent"),
)


def command(spec: Baseline, baseline: Path, runs: Path) -> list[str]:
    """Use the AEA CLI's privacy-guarded baseline creation path, not a log mock."""
    return [
        sys.executable, "-m", "agent_accelerator.cli", "check", spec.dataset,
        "--adapter", spec.adapter, "--agent", spec.agent,
        "--baseline", str(baseline), "--runs-dir", str(runs),
        "--max-samples", "1", *spec.flags, "--update-baseline",
    ]


def preflight(selected: tuple[Baseline, ...], output: Path = OUTPUT) -> None:
    """Fail closed if existing outputs or symlink parents could be overwritten."""
    if output.is_symlink() or not output.is_dir():
        raise ValueError(f"Expected a real existing directory at {output}")
    if not (output / "README.md").is_file():
        raise ValueError("baselines-new/README.md missing; check out the expected repository")
    for item in selected:
        target = output / item.name
        if target.exists() or target.is_symlink():
            raise FileExistsError(
                f"{target} already exists; archive or move it before regenerating"
            )
    if (output / "manifest.json").exists() or (output / "manifest.json").is_symlink():
        raise FileExistsError("Existing baselines-new/manifest.json must be archived before regeneration")


def dataset_count(dataset: Path) -> int:
    """Count source cases without reading prompts into persistent run metadata."""
    return sum(bool(line.strip()) for line in dataset.read_text(encoding="utf-8").splitlines())


def git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def manifest_entry(spec: Baseline, baseline: Path, root: Path = ROOT) -> dict:
    logs = sorted(baseline.glob("*.json"))
    if len(logs) != 1 or not (baseline / "report.md").is_file():
        raise RuntimeError(f"{spec.name}: expected one Inspect .json and report.md in {baseline}")
    log = logs[0]
    if log.is_symlink() or (baseline / "report.md").is_symlink():
        raise RuntimeError(f"{spec.name}: linked output is not allowed")
    dataset = root / spec.dataset
    return {
        "name": spec.name,
        "dataset": spec.dataset,
        "dataset_sha256": sha256(dataset.read_bytes()).hexdigest(),
        "case_count": dataset_count(dataset),
        "adapter": spec.adapter,
        "agent": spec.agent,
        "additional_cli_flags": list(spec.flags),
        "capture_content": False,
        "inspect_log_file": log.name,
        "inspect_log_sha256": sha256(log.read_bytes()).hexdigest(),
    }


def run(selected: tuple[Baseline, ...] = BASELINES, *, root: Path = ROOT,
        dry_run: bool = False) -> int:
    output = root / "baselines-new"
    preflight(selected, output)
    if not selected:
        raise ValueError("At least one agent is required")
    for spec in selected:
        if not (root / spec.dataset).is_file():
            raise FileNotFoundError(spec.dataset)
        print(f"NEW BASELINE: {spec.name} [{spec.adapter}] from {spec.dataset}", flush=True)
    if dry_run:
        print("DRY RUN: no new files were created", flush=True)
        return 0

    # A single staging workspace makes failures non-destructive to baselines-new.
    # The original baselines/ is never referenced as a write destination.
    with TemporaryDirectory(prefix=".aea-fresh-baseline-", dir=root) as temporary:
        stage = Path(temporary) / "baselines"
        stage.mkdir()
        runs = Path(temporary) / "runs"
        records = []
        env = dict(os.environ)
        env.update({
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            "AWS_SESSION_TOKEN": "",
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "PYTHONUTF8": "1",
        })
        for spec in selected:
            target = stage / spec.name
            process = subprocess.run(command(spec, target, runs), cwd=root, env=env, check=False)
            if process.returncode:
                raise RuntimeError(
                    f"{spec.name}: offline baseline failed with exit {process.returncode}; "
                    "no historical or existing baseline was overwritten"
                )
            records.append(manifest_entry(spec, target, root))

        manifest = {
            "schema": "aea-fresh-baselines-v1",
            "provenance": "reconstructed-offline-run; NOT a historical baseline",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "generator": "reconstruction_tools.generate_fresh_baselines",
            "git_revision": git_revision(root),
            "capture_content": False,
            "baselines": records,
        }
        # Refuse a late race with another generator. No existing baseline is removed.
        preflight(selected, output)
        for spec in selected:
            shutil.move(str(stage / spec.name), str(output / spec.name))
        (output / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"SUCCESS: {len(records)} freshly generated scrubbed baseline directories "
            "in baselines-new/; historical baselines/ unchanged",
            flush=True,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--only", choices=[b.name for b in BASELINES], nargs="+",
        help="Generate selected baselines only (default: all seven).",
    )
    args = parser.parse_args(argv)
    selected = tuple(b for b in BASELINES if args.only is None or b.name in args.only)
    try:
        return run(selected, dry_run=args.dry_run)
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError, OSError) as exc:
        print(f"FRESH BASELINES: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

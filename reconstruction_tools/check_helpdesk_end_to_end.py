"""Supplementary offline E2E smoke test for reconstructed helpdesk sources.

NOT the original missing tests/unit/test_helpdesk.py; it will be reconstructed
separately from user evidence. This tests the real AEA CLI, AEA case scoring
and LangGraph adapter against the 10 original screenshot cases.

The approval gate's regression variant MUST fail the two admin cases while
the correctly gated variant passes all 10 cases. No paid models or credentials.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from inspect_ai.log import read_eval_log

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import load_dataset
from agent_accelerator.judge import load_golden
from reconstruction_tools.verify_helpdesk_video_sources import verify

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "examples" / "helpdesk" / "dataset.jsonl"
GOLDEN = ROOT / "examples" / "helpdesk" / "golden.jsonl"
ADMIN_IDS = frozenset({"admin_local_docker", "admin_driver_update"})


def run(factory: str, temp_root: Path) -> tuple[set[str], dict[str, str]]:
    runs_dir = temp_root / factory
    cmd = [
        sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET),
        "--adapter", "langgraph", "--agent", f"examples.helpdesk.agent:{factory}",
        "--capture-content", "--max-samples", "2", "--runs-dir", str(runs_dir),
    ]
    env = {
        **os.environ, "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "", "PYTHONUTF8": "1",
    }
    outcome = subprocess.run(
        cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=240,
    )
    if outcome.returncode != 0:
        raise AssertionError(f"{factory} CLI failed ({outcome.returncode}):\n"
                             f"{outcome.stdout[-3000:]}\n{outcome.stderr[-5000:]}")
    saved = list(runs_dir.iterdir())
    if len(saved) != 1:
        raise AssertionError(f"{factory}: expected one run, got: {saved}")
    results = load_results(saved[0])
    all_ids = {case.id for case in load_dataset(DATASET)}
    if set(results.cases) != all_ids:
        raise AssertionError(f"{factory}: missing/extra cases: {set(results.cases) ^ all_ids}")
    failed = {i for i, case in results.cases.items() if not case.passed}
    log = read_eval_log(results.log_path)
    outputs = {str(s.id): s.output.completion for s in log.samples or []}
    if set(outputs) != all_ids:
        raise AssertionError(f"{factory}: log samples missing: {set(outputs) ^ all_ids}")
    print(f"{factory}: {len(results.cases)} cases; failures={sorted(failed)}", flush=True)
    return failed, outputs


def main() -> None:
    verify()
    ids = {case.id for case in load_dataset(DATASET)}
    golden = load_golden(GOLDEN, ids)
    if len(ids) != 10 or len(golden) != 6:
        raise AssertionError("Original helpdesk screenshot dataset or reference count changed")
    with TemporaryDirectory(prefix="aea_helpdesk_") as d:
        temp_root = Path(d)
        gated_fail, gated_outputs = run("build_agent", temp_root)
        if gated_fail:
            raise AssertionError(f"Gated original helpdesk should pass all 10 cases: {sorted(gated_fail)}")
        if {case_id: gated_outputs[case_id] for case_id in golden} != {
            case_id: item.reference for case_id, item in golden.items()
        }:
            mismatches = {
                key: (gated_outputs[key], golden[key].reference)
                for key in golden if gated_outputs[key] != golden[key].reference
            }
            raise AssertionError(f"Original screenshot golden references diverge: {mismatches}")
        ungated_fail, _ = run("build_ungated_agent", temp_root)
        if ungated_fail != ADMIN_IDS:
            raise AssertionError(f"Approval-gate regression must fail exactly {sorted(ADMIN_IDS)}, "
                                 f"found {sorted(ungated_fail)}")
    print("PASS: original helpdesk 10-case dataset, 6 exact golden outputs and 2-case approval-gate regression")


if __name__ == "__main__":
    main()

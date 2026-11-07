"""Run original policy RAG screenshot cases through native AEA CLI offline.

Supplementary reconstruction validation only, NOT the recorded historical
tests/unit/test_policy_rag.py source. The original user test video will be
transcribed and verified separately, without overwriting that evidence.

The good model must ground all 11 cases in the policy excerpts. The confident
variant's fabricated hotel figure must fail exactly the two hotel examples.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from inspect_ai.log import read_eval_log

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import load_dataset
from agent_accelerator.judge import load_golden
from reconstruction_tools.verify_policy_rag_video_sources import check

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "examples" / "policy_rag" / "dataset.jsonl"
GOLDEN = ROOT / "examples" / "policy_rag" / "golden.jsonl"
HALLUCINATED_HOTELS = {"hotel_cap_tier1_city", "hotel_cap_other_city"}


def run(factory: str, directory: Path) -> tuple[set[str], dict[str, str]]:
    runs_dir = directory / factory
    cmd = [
        sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET),
        "--adapter", "langgraph", "--agent", f"examples.policy_rag.agent:{factory}",
        "--capture-content", "--max-samples", "2", "--runs-dir", str(runs_dir),
    ]
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
    }
    completed = subprocess.run(
        cmd, cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=240,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"{factory}: AEA CLI failed {completed.returncode}\n"
            f"{completed.stdout[-3000:]}\n{completed.stderr[-6000:]}"
        )
    run_entries = list(runs_dir.iterdir())
    if len(run_entries) != 1:
        raise AssertionError(f"{factory}: expected one run directory: {run_entries}")
    results = load_results(run_entries[0])
    expected_ids = {x.id for x in load_dataset(DATASET)}
    if set(results.cases) != expected_ids:
        raise AssertionError(f"{factory}: missing IDs: {expected_ids ^ set(results.cases)}")
    failed = {i for i, case in results.cases.items() if not case.passed}
    inspect_log = read_eval_log(results.log_path)
    outputs = {str(sample.id): sample.output.completion for sample in inspect_log.samples or []}
    if set(outputs) != expected_ids:
        raise AssertionError(f"{factory}: missing Inspect log completions")
    print(f"PASS CLI {factory}: all {len(results.cases)} cases present, failures={sorted(failed)}", flush=True)
    return failed, outputs


def main() -> None:
    check()
    case_ids = {case.id for case in load_dataset(DATASET)}
    golden = load_golden(GOLDEN, case_ids)
    with TemporaryDirectory(prefix="aea_policy_rag_") as folder:
        directory = Path(folder)
        good_fails, good_outputs = run("build_agent", directory)
        if good_fails:
            raise AssertionError(f"Good policy-grounded agent unexpectedly failed: {sorted(good_fails)}")
        mismatches = {
            k: (good_outputs[k], g.reference)
            for k, g in golden.items() if good_outputs[k] != g.reference
        }
        if mismatches:
            raise AssertionError(f"Screenshot golden references differ from grounded replies: {mismatches}")
        bad_fails, bad_outputs = run("build_confident_agent", directory)
        if bad_fails != HALLUCINATED_HOTELS:
            raise AssertionError(
                "Confident prompt must fail exactly the two hotel-reference cases; "
                f"actual failures={sorted(bad_fails)}"
            )
        for k in HALLUCINATED_HOTELS:
            if "USD 300" not in bad_outputs[k]:
                raise AssertionError(f"{k}: no evidence of intended hallucinated hotel figure")

    print("PASS: policy RAG 11-case grounded CLI, 6 exact references, two seeded hotel hallucinations")


if __name__ == "__main__":
    main()

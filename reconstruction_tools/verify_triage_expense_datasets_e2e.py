"""Native offline end-to-end execution of the video-recovered 12-case datasets.

Real AEA CLI + original screenshot/video-derived simulated LangGraph agents,
not fixture stand-ins or the missing historical Inspect captured JSON files.
All new evaluation logs live in a disposable temporary directory. Never
invoke triage's optional AWS-backed build_live_agent constructor.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import load_dataset

ROOT = Path(__file__).resolve().parents[1]


def verify_agent(name: str, temp: Path) -> None:
    dataset = ROOT / "examples" / name / "dataset.jsonl"
    config = ROOT / "examples" / name / "aea.toml"
    original_cases = load_dataset(dataset)
    runs = temp / name
    env = {**os.environ, "AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"}
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        env[key] = ""
    proc = subprocess.run(
        [
            sys.executable, "-m", "agent_accelerator.cli",
            "run", str(dataset), "--config", str(config),
            "--runs-dir", str(runs), "--max-samples", "1",
        ],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"Recovered {name} CLI run failed with {proc.returncode}:\n"
            f"{proc.stdout[-5000:]}\n{proc.stderr[-5000:]}"
        )
    folders = [p for p in runs.iterdir() if p.is_dir()]
    if len(folders) != 1:
        raise AssertionError(f"{name}: expected exactly one offline results folder: {folders}")
    result = load_results(folders[0])
    actual = set(result.cases)
    expected = {case.id for case in original_cases}
    if actual != expected or len(actual) != 12:
        raise AssertionError(
            f"{name}: 12 recorded case IDs not preserved: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    if result.status != "success":
        raise AssertionError(f"{name}: AEA offline run status {result.status}:\n{proc.stdout[-5000:]}")
    failed = [key for key, case in result.cases.items() if not case.passed]
    if failed:
        raise AssertionError(
            f"{name}: source-recovered good agent failed {len(failed)}/12 recorded cases: "
            f"{failed}\n{proc.stdout[-6000:]}"
        )
    if result.capture_content:
        raise AssertionError(f"{name}: offline CI must not retain case inputs in traces")
    print(f"PASS {name}: AEA real offline LangGraph run; 12/12 recorded cases and source contracts", flush=True)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aea-recovered-video-datasets-") as td:
        for name in ("triage", "expense"):
            verify_agent(name, Path(td))
    print(
        "No paid providers, credentials, cloud or historical captured JSON substitutes used.",
        flush=True,
    )


if __name__ == "__main__":
    main()

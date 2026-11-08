"""Replay selected fixture-independent original expense and triage candidate tests.

Original-path files must equal the pinned provisional video drafts. The source
files and recorded assertions are not rewritten, and no paid provider is used.
This is a runtime replay, not a claim of byte-for-byte video transcription.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from reconstruction_tools.replay_original_video_test_candidates import (
    EXPENSE_TESTS,
    TRIAGE_TESTS,
)
from reconstruction_tools.verify_original_video_test_candidates import validate_source

ROOT = Path(__file__).resolve().parents[1]


def run(name: str) -> int:
    source, _ = validate_source(name)
    path = ROOT / "tests" / "unit" / f"test_{name}.py"
    if not path.is_file():
        raise RuntimeError(f"Historical-path candidate absent: {path}")
    if path.read_text(encoding="utf-8") != source:
        raise RuntimeError(f"Original-path {name} test diverges from pinned video candidate")
    names = TRIAGE_TESTS if name == "triage" else EXPENSE_TESTS
    env = dict(os.environ)
    env.update({
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "PYTHONUTF8": "1",
    })
    relative = path.relative_to(ROOT).as_posix()
    command = [sys.executable, "-m", "pytest", "-q", "-m", "not slow", "--maxfail=1"]
    command.extend(f"{relative}::{test_name}" for test_name in names)
    print(f"Replaying {len(names)} recorded {name} tests from {relative}", flush=True)
    return subprocess.call(command, cwd=ROOT, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("expense", "triage", "all"), default="all")
    args = parser.parse_args()
    selected = ("triage", "expense") if args.suite == "all" else (args.suite,)
    return int(any(run(name) != 0 for name in selected))


if __name__ == "__main__":
    raise SystemExit(main())

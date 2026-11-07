"""Replay the original recorded golden tests unchanged against screenshot sources.

The user-provided full source videos for test_triage.py / test_expense.py were
transcribed to immutable reconstruction_drafts. Their original golden tests
refer to repo-relative examples/*/golden.jsonl. Temporary copies are staged
in tests/unit only to preserve the original REPO calculation; the original
video-derived source text and assertions are never changed.

No cloud credentials, paid providers or historical fixture substitutes.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from reconstruction_tools.verify_original_video_test_candidates import validate_source
from reconstruction_tools.verify_triage_expense_golden_screenshots import main as verify_goldens

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "tests" / "unit"
SELECTIONS = {
    "triage": (
        "test_golden_has_six_references_five_labelled_each_matching_the_good_agents_answer",
    ),
    "expense": (
        "test_golden_covers_eight_dataset_cases_with_five_labelled_and_the_three_referrals_unlabelled",
        "test_every_golden_reference_is_the_reply_the_agent_gives_for_its_case",
    ),
}


def replay(name: str) -> int:
    source, tree = validate_source(name)
    tests = SELECTIONS[name]
    original_tests = {
        node.name for node in tree.body
        if node.__class__.__name__ in ("FunctionDef", "AsyncFunctionDef")
        and node.name.startswith("test_")
    }
    if not set(tests) <= original_tests:
        raise AssertionError(f"{name}: golden test names missing from original video draft")
    path = STAGED / f"test_{name}_golden_REPLAY_TEMP.py"
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"Refuse to overwrite source file: {path}")
    path.write_text(source, encoding="utf-8", newline="\n")
    rel = path.relative_to(ROOT).as_posix()
    commands = [
        sys.executable, "-m", "pytest", "-q", "-m", "not slow", "--maxfail=1",
        *[f"{rel}::{name_of_test}" for name_of_test in tests],
    ]
    env = {
        **os.environ,
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "", "PYTHONUTF8": "1",
    }
    print(f"Replaying {len(tests)} unchanged original video {name} golden test(s).", flush=True)
    try:
        return subprocess.call(commands, cwd=ROOT, env=env)
    finally:
        path.unlink(missing_ok=True)


def main() -> int:
    verify_goldens()
    bad = [name for name in SELECTIONS if replay(name) != 0]
    if bad:
        print(f"Original video golden replay FAILED: {bad}", file=sys.stderr)
        return 1
    print(
        "PASS: original video-derived golden tests pass on screenshot-derived "
        "references. Historical file-byte equality remains unproven.", flush=True
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

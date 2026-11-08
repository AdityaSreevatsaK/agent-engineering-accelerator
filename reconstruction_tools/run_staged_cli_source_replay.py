"""Run known fixture-independent recorded CLI tests from the original-path candidate.

No synthetic original fixtures, cloud calls, or modifications to test source.
This is a focused functional replay, not historical source-fidelity certification.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from reconstruction_tools.run_original_cli_fast_replay import (
    REPLAY_TESTS,
    ROOT,
    SOURCE,
    validate_source,
)

ACTIVE = ROOT / "tests" / "unit" / "test_cli.py"


def main() -> int:
    validate_source()
    if not ACTIVE.is_file():
        raise RuntimeError(f"Staged source missing: {ACTIVE}")
    if ACTIVE.read_text(encoding="utf-8") != SOURCE.read_text(encoding="utf-8"):
        raise RuntimeError("Staged CLI source diverges from pinned provisional video candidate")
    argv = [
        sys.executable, "-m", "pytest", "-q", "-m", "not slow",
        *(f"{ACTIVE.relative_to(ROOT).as_posix()}::{name}" for name in REPLAY_TESTS),
    ]
    env = dict(os.environ)
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    print(f"Replaying {len(REPLAY_TESTS)} recorded CLI test functions from staged original path", flush=True)
    return subprocess.call(argv, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())

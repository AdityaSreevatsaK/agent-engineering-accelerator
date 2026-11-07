"""Replay source-recorded comparison tests using disposable, real offline AEA logs.

These original test functions are deliberately deferred from the integrated
CI because two *historical* Inspect logs have not been recovered. This
separate verification lane runs the actual video-recovered calculator twice:
10/10 with capture-content, then 8/10 broken without capture, and stages
their genuine runtime logs in an isolated TemporaryDirectory.

ONLY a temporary test copy changes the FIXTURES directory reference. All
recorded test function bodies, assertions and parameterisations remain
unchanged; no original fixture is forged, overwritten, or committed.
Passing results validate reconstructed behaviour, NOT historical fixture
provenance, visual fidelity, or a completed original file inventory.
"""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from agent_accelerator.compare import load_results
from reconstruction_tools.run_compare_without_original_fixtures import DEFERRED, preflight

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"
FIXTURE_ANCHOR = 'FIXTURES = Path(__file__).parents[1] / "fixtures"'
REPLAY_VAR = "AEA_REPLAY_GENERATED_COMPARISON_FIXTURES_NOT_ORIGINAL"
FILES = {
    "tests/unit/test_compare.py": (
        "tests/unit/test_compare_fixture_replay_TEMP.py",
        "a615b5d626b3ff95ab6ce5078d23b90325784507",
    ),
    "tests/unit/test_compare_statistics.py": (
        "tests/unit/test_compare_statistics_fixture_replay_TEMP.py",
        "dc36c1d5845b62855a3b32e5c7f8acd3ceb8fdf2",
    ),
}
EXPECTED_DEFERRED = {"tests/unit/test_compare.py": 30, "tests/unit/test_compare_statistics.py": 2}


def source_blob_sha(text: str) -> str:
    data = text.encode("utf-8")  # normalised LF on Windows and Linux
    return hashlib.sha1(f"blob {len(data)}\\0".encode().replace(b"\\0", b"\\x00") + data).hexdigest()


def cli_run(runs_dir: Path, builder: str, capture: bool) -> Path:
    env = os.environ.copy()
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    env["PYTHONUTF8"] = "1"
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        env[key] = ""
    args = [
        sys.executable, "-m", "agent_accelerator.cli",
        "run", str(DATASET), "--agent", f"examples.calculator.agent:{builder}",
        "--adapter", "strands", "--runs-dir", str(runs_dir),
    ]
    if capture:
        args.append("--capture-content")
    proc = subprocess.run(
        args, cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=240, check=False,
    )
    tally = "passed=10/10" if capture else "passed=8/10"
    if proc.returncode != 0 or tally not in proc.stdout:
        raise RuntimeError(
            f"Offline calculator {builder} did not produce {tally}: "
            f"exit {proc.returncode}\\nstdout:\\n{proc.stdout[-3500:]}\\n"
            f"stderr:\\n{proc.stderr[-3500:]}"
        )
    directories = [p for p in runs_dir.iterdir() if p.is_dir()]
    if len(directories) != 1:
        raise RuntimeError(f"Expected one offline result directory, got {directories}")
    logs = list(directories[0].glob("*.json"))
    if len(logs) != 1:
        raise RuntimeError(f"Expected one offline Inspect JSON log, got {logs}")
    return logs[0]


def make_generated_fixture_directory(folder: Path) -> Path:
    if not DATASET.is_file():
        raise RuntimeError("Recovered original calculator dataset unavailable")
    source_dir = folder / "real-calculator-runs"
    normal_log = cli_run(source_dir / "capture", "build_agent", capture=True)
    broken_log = cli_run(source_dir / "broken", "build_broken_agent", capture=False)
    baseline = load_results(normal_log)
    broken = load_results(broken_log)
    if (
        len(baseline.cases) != 10
        or any(not case.passed or case.error is not None for case in baseline.cases.values())
        or not baseline.capture_content
        or not isinstance(baseline.dataset_sha256, str)
        or len(baseline.dataset_sha256) != 64
    ):
        raise RuntimeError("Generated captured normal log does not meet recorded calculator invariants")
    if (
        len(broken.cases) != 10
        or broken.capture_content
        or broken.status != "success"
        or {name for name, case in broken.cases.items() if not case.passed}
        != {"subtract", "subtract_large"}
        or baseline.dataset_sha256 != broken.dataset_sha256
    ):
        raise RuntimeError("Generated broken log does not meet recorded regression invariants")
    fixtures = folder / "REPLAY_GENERATED_NOT_HISTORICAL_FIXTURES"
    fixtures.mkdir()
    shutil.copyfile(normal_log, fixtures / "calculator_capture_content.json")
    shutil.copyfile(broken_log, fixtures / "calculator_broken_redacted.json")
    print(
        "Generated disposable ORIGINAL-AGENT runtime logs: normal 10/10 (capture) "
        "and broken 8/10 (redacted). NOT historic fixture bytes.",
        flush=True,
    )
    return fixtures


def stage_recorded_tests() -> dict[str, Path]:
    if set(FILES) != set(DEFERRED):
        raise RuntimeError("Recorded comparison manifest or staging map changed")
    if {name: len(names) for name, names in DEFERRED.items()} != EXPECTED_DEFERRED:
        raise RuntimeError("Historical fixture-dependent deferral inventory changed")
    preflight()
    staged: dict[str, Path] = {}
    for path, (temporary_path, expected_sha) in FILES.items():
        full_path = ROOT / path
        source = full_path.read_text(encoding="utf-8")
        if source_blob_sha(source) != expected_sha:
            raise RuntimeError(f"Recovered test source drifted: {path}; review fidelity")
        if source.count(FIXTURE_ANCHOR) != 1:
            raise RuntimeError(f"Recorded fixture declaration changed: {path}")
        tree = ast.parse(source, filename=str(full_path), feature_version=(3, 11))
        test_definitions = {
            node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        }
        if not set(DEFERRED[path]) <= test_definitions.keys():
            raise RuntimeError(f"Historical deferred test names changed: {path}")
        for name in DEFERRED[path]:
            fn = test_definitions[name]
            fixture_names = {arg.arg for arg in [
                *fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs
            ]}
            if fixture_names & {"runs", "check_runs", "price_runs"}:
                raise RuntimeError(f"Cannot run subprocess-fixture dependent test: {path}::{name}")

        temp_path = ROOT / temporary_path
        if temp_path.exists() or temp_path.is_symlink():
            raise RuntimeError(f"Will not overwrite existing test file: {temp_path}")
        patched = source.replace(
            FIXTURE_ANCHOR,
            FIXTURE_ANCHOR
            + "\\n# REPLAY-ONLY: source assertions unchanged, use temporary actual runtime logs\\n"
            + f'FIXTURES = Path(__import__("os").environ["{REPLAY_VAR}"])',
            1,
        )
        ast.parse(patched, filename=str(temp_path), feature_version=(3, 11))
        temp_path.write_text(patched, encoding="utf-8", newline="\\n")
        staged[path] = temp_path
    return staged


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aea-compare-REPLAY-GENERATED-") as td:
        fixtures = make_generated_fixture_directory(Path(td))
        staged: dict[str, Path] = {}
        try:
            staged = stage_recorded_tests()
            args = [
                sys.executable, "-m", "pytest", "-q", "-o", "addopts=",
                "--color=no", "--maxfail=1",
            ]
            for path, temporary in staged.items():
                args.extend(
                    f"{temporary.relative_to(ROOT).as_posix()}::{name}"
                    for name in DEFERRED[path]
                )
            env = {**os.environ, REPLAY_VAR: str(fixtures), "AWS_EC2_METADATA_DISABLED": "true"}
            for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
                env[key] = ""
            print(
                "Replaying 32 originally deferred test functions with genuine "
                "temporary offline runs, not recovered original fixtures.",
                flush=True,
            )
            return subprocess.call(args, cwd=ROOT, env=env)
        finally:
            for path in staged.values():
                path.unlink(missing_ok=True)
            # If staging failed after writing one file, remove ONLY the
            # explicitly named temporary files created by this script.
            for temporary_path, _ in FILES.values():
                staged_path = ROOT / temporary_path
                if staged_path.is_file() and staged_path not in staged.values():
                    staged_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

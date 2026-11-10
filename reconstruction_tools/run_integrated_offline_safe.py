"""Run AEA's recovered offline unit suite with a disposable synthetic fixture.

The original calculator_capture_content.json is unavailable. This runner
generates CI-only Inspect fixture bytes using the existing native generator,
checks for collisions with real files, and removes generated data afterwards.
It never claims to recover the original fixture or original baselines.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = Path("tests/fixtures/calculator_capture_content.json")
EVALUATION_DIR = Path("tests/fixtures/.temporary_synthetic_evaluation")

Runner = Callable[[list[str], Path], int]


def run_python(args: list[str], cwd: Path) -> int:
    return subprocess.call([sys.executable, "-m", *args], cwd=cwd)


def preflight(root: Path) -> None:
    """Fail closed rather than overwriting existing or linked source evidence."""
    for rel in (CAPTURE, EVALUATION_DIR):
        target = root / rel
        if target.exists() or target.is_symlink():
            raise FileExistsError(
                f"Refusing to overwrite existing data at {target}; "
                "inspect original source evidence manually"
            )
        for parent in target.parents:
            if parent == root:
                break
            if parent.is_symlink():
                raise ValueError(f"Refusing fixture path through symlink: {parent}")


def run(*, root: Path = ROOT, runner: Runner = run_python) -> int:
    """Execute generator + integrated tests, then remove only our generated data."""
    preflight(root)
    fixture = root / CAPTURE
    work_dir = root / EVALUATION_DIR
    generator_finished = False
    digest: str | None = None
    try:
        code = runner(["reconstruction_tools.make_synthetic_capture"], root)
        if code:
            # A failed generator may have left partial evidence; do not delete
            # a file we cannot prove was generated successfully.
            return code
        generator_finished = True
        if fixture.is_symlink() or not fixture.is_file():
            raise RuntimeError("Synthetic fixture generator returned successfully without a safe file")
        digest = sha256(fixture.read_bytes()).hexdigest()
        print(
            "SYNTHETIC ONLY: captured fixture generated for the temporary "
            "native unit-suite run; original historical fixture remains unavailable.",
            flush=True,
        )
        return runner(["reconstruction_tools.run_integrated_offline"], root)
    finally:
        if generator_finished:
            if fixture.is_symlink() or not fixture.is_file():
                raise RuntimeError("Temporary synthetic fixture disappeared or became linked; refusing cleanup")
            if digest is None or sha256(fixture.read_bytes()).hexdigest() != digest:
                raise RuntimeError("Temporary synthetic fixture changed during tests; refusing automatic deletion")
            fixture.unlink()
            if work_dir.is_symlink():
                raise RuntimeError("Synthetic evaluation folder became linked; refusing automatic deletion")
            if work_dir.is_dir():
                shutil.rmtree(work_dir)
            elif work_dir.exists():
                raise RuntimeError("Unexpected synthetic evaluation output type; review manually")
            print(
                "CLEANUP: deleted generated synthetic capture and evaluation "
                "logs; no historical fixture was reconstructed.",
                flush=True,
            )


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

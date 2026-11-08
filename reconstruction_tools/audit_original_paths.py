"""Audit original AEA v2.2.0 path presence without claiming source fidelity.

The canonical 117 historical paths are preserved in
reconstruction_manifest/original_paths.txt. Only files actually tracked at
their original paths count. Reconstruction drafts, generated traces and helper
files do not count; fixture contents are not inspected or fabricated.

Requires the standard-library Python 3.11+ and a Git checkout. Safe offline.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "reconstruction_manifest" / "original_paths.txt"
EXPECTED = {
    "CI": 1,
    "Baselines": 14,
    "Documentation": 2,
    "Examples": 31,
    "Scripts": 1,
    "Source": 23,
    "Tests": 39,
    "Root": 6,
}


def classify(path: str) -> str:
    if path.startswith(".github/"):
        return "CI"
    if path.startswith("baselines/"):
        return "Baselines"
    if path.startswith("docs/"):
        return "Documentation"
    if path.startswith("examples/"):
        return "Examples"
    if path.startswith("scripts/"):
        return "Scripts"
    if path.startswith("src/"):
        return "Source"
    if path.startswith("tests/"):
        return "Tests"
    return "Root"


def load_inventory(path: Path = INVENTORY) -> tuple[str, ...]:
    paths = tuple(
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if len(paths) != 117:
        raise ValueError(f"Expected 117 historical paths, got {len(paths)}")
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate historical paths")
    for item in paths:
        pure = PurePosixPath(item)
        if (item.startswith("/") or "\\" in item or item.strip() != item
                or len(pure.parts) == 0 or any(part in ("..", ".") for part in item.split("/"))
                or any(part == "" for part in item.split("/"))):
            raise ValueError(f"Unsafe or noncanonical historical path: {item!r}")
    counts = Counter(classify(item) for item in paths)
    if dict(counts) != EXPECTED:
        raise ValueError(f"Category counts drifted: {dict(counts)!r}")
    return paths


def tracked_files(root: Path = ROOT) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z"],
        capture_output=True, check=True,
    )
    return {part.decode("utf-8") for part in result.stdout.split(b"\x00") if part}


def summarise(paths: tuple[str, ...], tracked: set[str]) -> dict:
    present = sorted(set(paths) & tracked)
    absent = sorted(set(paths) - tracked)
    by_category = {}
    for category in EXPECTED:
        members = [path for path in paths if classify(path) == category]
        count = sum(path in tracked for path in members)
        by_category[category] = {
            "expected": len(members),
            "present": count,
            "missing": len(members) - count,
        }
    return {
        "expected_original_paths": len(paths),
        "present_original_paths": len(present),
        "missing_original_paths": len(absent),
        "by_category": by_category,
        "present": present,
        "missing": absent,
        "warning": "Presence only; not evidence of exact source fidelity, successful runtime, or release readiness.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--minimum-present", type=int, default=83,
                        help="Fail if recorded paths regress below 8 Nov 2026 checkpoint (83)")
    parser.add_argument("--show-missing", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable report")
    args = parser.parse_args(argv)
    try:
        paths = load_inventory(args.root / "reconstruction_manifest" / "original_paths.txt")
        result = summarise(paths, tracked_files(args.root))
    except (ValueError, OSError, subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        print(f"INVENTORY AUDIT FAILED: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Historical AEA paths: {result['present_original_paths']}/"
              f"{result['expected_original_paths']} present; "
              f"{result['missing_original_paths']} missing")
        for category, counts in result["by_category"].items():
            print(f"  {category:15} {counts['present']:2}/{counts['expected']:2} present")
        print("Presence != source-byte fidelity or production readiness.")
        if args.show_missing:
            print("Missing original paths:")
            for name in result["missing"]:
                print(f"  {name}")
    if result["present_original_paths"] < args.minimum_present:
        print(
            f"REGRESSION: {result['present_original_paths']} present, "
            f"checkpoint minimum {args.minimum_present}", file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

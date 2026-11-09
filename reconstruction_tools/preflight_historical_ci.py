"""Offline safety gate for activating recorded historical AEA ci.yml.

Historical path presence is not proof of source fidelity or release readiness.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import tomllib

from reconstruction_tools.audit_original_paths import load_inventory

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = Path(".github/workflows/ci.yml")
ARCHIVE = Path("reconstruction_drafts/original_github_workflows_ci.yml.txt")
FIXTURES = (
    "tests/fixtures/calculator_capture_content.json",
    "tests/fixtures/calculator_broken_redacted.json",
)


def is_safe_file(root: Path, path: str | Path) -> bool:
    target = root / path
    current = target
    while current != root:
        if current.is_symlink() or current == current.parent:
            return False
        current = current.parent
    return target.is_file()


def inspect(root: Path = ROOT) -> dict:
    originals = load_inventory(root / "reconstruction_manifest/original_paths.txt")
    required = sorted(
        [p for p in originals if p.startswith("baselines/")]
        + ["uv.lock", *FIXTURES]
    )
    missing = [p for p in required if not is_safe_file(root, p)]
    issues: list[str] = []
    active = (root / ORIGINAL).exists() or (root / ORIGINAL).is_symlink()

    if not is_safe_file(root, ARCHIVE):
        issues.append("Preserved original CI recording is missing or unsafe")
    elif active:
        if not is_safe_file(root, ORIGINAL):
            issues.append("Active CI workflow is linked or not a regular file")
        else:
            archived = (root / ARCHIVE).read_text(encoding="utf-8")
            actual = (root / ORIGINAL).read_text(encoding="utf-8")
            if archived.replace("\r\n", "\n") != actual.replace("\r\n", "\n"):
                issues.append("Active CI differs from preserved recorded workflow")

    if is_safe_file(root, "uv.lock"):
        try:
            with (root / "uv.lock").open("rb") as handle:
                lock = tomllib.load(handle)
            if not isinstance(lock.get("package"), list) or not lock["package"]:
                issues.append("uv.lock lacks resolved packages")
        except (OSError, ValueError, tomllib.TOMLDecodeError):
            issues.append("uv.lock is invalid TOML")
    return {"active": active, "missing": missing, "issues": issues}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    report = inspect(args.root)
    print(f"Historical CI active: {report['active']}; "
          f"prerequisites missing or unsafe: {len(report['missing'])}")
    for item in report["missing"]:
        print(f"  {item}")
    for item in report["issues"]:
        print(f"  ERROR: {item}")
    print("Presence alone does not authenticate historical sources or approve release.")
    return int(bool(report["issues"] or (report["active"] and report["missing"])))


if __name__ == "__main__":
    raise SystemExit(main())

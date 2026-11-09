"""Reproducible, fail-closed AEA reconstruction and release evidence snapshot.

This checks historical path presence and safe local prerequisites only.
It does NOT prove original source-video fidelity or historical log authenticity.
Offline, Python >=3.11, stdlib only. Never reads historical traces/captures.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from reconstruction_tools.audit_original_paths import ROOT, load_inventory, summarise, tracked_files
from reconstruction_tools.preflight_historical_ci import inspect as inspect_ci
from reconstruction_tools.preflight_historical_ci import is_safe_file

DOCUMENT_DRAFTS = {
    "docs/acceptance.md": "reconstruction_drafts/docs_acceptance_video_PROVISIONAL.md",
    "docs/review.md": "reconstruction_drafts/docs_review_video_PROVISIONAL.md",
}
WORKFLOW_ARCHIVE = "reconstruction_drafts/original_github_workflows_ci.yml.txt"
MANUAL_GATES = (
    "Review video transcriptions against original footage including ambiguous lines.",
    "Review authentic baselines and calculator fixtures for privacy and provenance.",
    "Run historical locked CI with authentic inputs, slow and integration tests.",
    "Complete operator documentation, security review and formal release acceptance.",
)


def inspect(root: Path = ROOT, *, tracked: set[str] | None = None) -> dict:
    """Report actual recoverability without silently granting release approval."""
    root = root.resolve()
    inventory = load_inventory(root / "reconstruction_manifest/original_paths.txt")
    paths = summarise(inventory, tracked if tracked is not None else tracked_files(root))
    tracked_present = paths["present"]
    unreadable = [p for p in tracked_present if not is_safe_file(root, p)]
    ci = inspect_ci(root)
    docs = {
        original: {
            "original_present": original in tracked_present and is_safe_file(root, original),
            "provisional_draft_present": is_safe_file(root, draft),
            "provisional_draft_path": draft,
        }
        for original, draft in DOCUMENT_DRAFTS.items()
    }
    if is_safe_file(root, "README.md"):
        readme_stub = (root / "README.md").read_text(encoding="utf-8").strip() == "# agent-engineering-accelerator"
    else:
        readme_stub = True

    blockers: list[str] = []
    if paths["missing"]:
        blockers.append(f"{len(paths['missing'])} historical file paths are absent")
    if unreadable:
        blockers.append(f"{len(unreadable)} tracked original files are missing/linked on disk")
    if ci["missing"]:
        blockers.append(f"{len(ci['missing'])} historical CI prerequisites are absent or unsafe")
    if ci["issues"]:
        blockers.extend(f"Historical CI preflight: {issue}" for issue in ci["issues"])
    if not ci["active"]:
        blockers.append("Historical original CI is archived and not active")
    if readme_stub:
        blockers.append("The historical root README remains a title-only stub")
    if any(not record["original_present"] for record in docs.values()):
        blockers.append("Original acceptance and/or security-review documents are not restored")

    return {
        "scope": "Offline local path and prerequisite evidence; never original byte fidelity",
        "historical_inventory": {
            "expected": paths["expected_original_paths"],
            "present": paths["present_original_paths"],
            "missing": paths["missing_original_paths"],
            "by_category": paths["by_category"],
            "missing_paths": paths["missing"],
            "tracked_but_missing_or_linked": unreadable,
        },
        "historical_ci": {
            "active": ci["active"],
            "archive_present": is_safe_file(root, WORKFLOW_ARCHIVE),
            "missing_or_unsafe_prerequisites": ci["missing"],
            "preflight_issues": ci["issues"],
        },
        "documentation": {"root_readme_is_stub": readme_stub, "historical_docs": docs},
        "release": {
            "state": "blocked" if blockers else "requires_manual_review",
            "blockers": blockers,
            "manual_evidence_gates": list(MANUAL_GATES),
            "automatic_source_byte_fidelity_certified": False,
            "approved_for_master": False,
        },
        "warning": "Presence and successful reconstructed CI cannot establish historic byte fidelity or release readiness.",
    }


def render_markdown(result: dict) -> str:
    inv = result["historical_inventory"]
    release = result["release"]
    lines = [
        "# AEA reconstruction release-evidence snapshot",
        "",
        f"Status: {release['state']}",
        f"Original files present: {inv['present']}/{inv['expected']}",
        "",
        "| Category | Present | Expected |",
        "| --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {category} | {group['present']} | {group['expected']} |"
        for category, group in inv["by_category"].items()
    )
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {name}" for name in release["blockers"])
    lines.extend(["", "## Missing historical paths", ""])
    lines.extend(f"- {path}" for path in inv["missing_paths"])
    lines.extend(["", "## Manual evidence still required", ""])
    lines.extend(f"- {name}" for name in release["manual_evidence_gates"])
    lines.extend(["", "Automatic source-byte certification: no", "Approved for master: no", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument(
        "--require-release-ready", action="store_true",
        help="Fail closed: automatic file evidence alone never signs off original fidelity",
    )
    args = parser.parse_args(argv)
    try:
        result = inspect(args.root)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        print(f"AEA readiness audit error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.format == "markdown":
        print(render_markdown(result))
    else:
        inv = result["historical_inventory"]
        print(f"AEA release readiness: {result['release']['state']}; "
              f"{inv['present']}/{inv['expected']} historical paths")
        for issue in result["release"]["blockers"]:
            print(f"  BLOCKER: {issue}")
        print(result["warning"])
    if args.require_release_ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

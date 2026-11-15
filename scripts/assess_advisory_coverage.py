"""Compare observed advisory coverage with the complete locked dependency list.

Read-only coverage report. Unscanned packages are explicitly identified, including
platform variants and development dependencies. Does not approve packages.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _identity(name: str, version: str) -> tuple[str, str]:
    if not name or not version:
        raise ValueError("package has no name or version")
    return re.sub(r"[-_.]+", "-", name).lower(), version


def assess(sbom: dict[str, Any], scan: dict[str, Any]) -> dict[str, Any]:
    """Verify audit provenance and describe gaps without conflating lock and runtime."""
    locked_records = sbom.get("packages")
    audited_records = scan.get("scanned_packages")
    if not isinstance(locked_records, list) or not locked_records:
        raise ValueError("dependency BOM contains no locked package records")
    if not isinstance(audited_records, list) or not audited_records:
        raise ValueError("advisory evidence lacks individually identified scanned packages")
    locked: set[tuple[str, str]] = set()
    installed: set[tuple[str, str]] = set()
    for entry in locked_records:
        if not isinstance(entry, dict):
            raise ValueError("invalid locked package")
        item = _identity(entry.get("name"), entry.get("version"))
        if item in locked:
            raise ValueError("duplicate locked package")
        locked.add(item)
        if entry.get("installed") is True:
            installed.add(item)
        elif entry.get("installed") is not False:
            raise ValueError("invalid installed-package selection status")
    audited: set[tuple[str, str]] = set()
    for entry in audited_records:
        if not isinstance(entry, dict):
            raise ValueError("invalid audited package")
        item = _identity(entry.get("name"), entry.get("version"))
        if item in audited:
            raise ValueError("duplicate audited package")
        audited.add(item)
    if len(locked) != sbom.get("locked_registry_entries"):
        raise ValueError("incomplete locked package inventory")
    if len(audited) != scan.get("scanned_package_entries"):
        raise ValueError("incomplete audited package inventory")
    if len(installed) != sbom.get("installed_locked_entries"):
        raise ValueError("incomplete installed package inventory")
    unexpected = sorted(audited - locked)
    if unexpected:
        raise ValueError(f"audited dependencies not present at locked versions: {unexpected}")
    if scan.get("security_approved") is not False or sbom.get("independent_security_signoff") is not False:
        raise ValueError("review-only inputs must not claim approval")
    if scan.get("status") not in {"no_known_findings_in_scanned_set", "findings_require_review"}:
        raise ValueError("unrecognised advisory scan status")
    def pairs(items: set[tuple[str, str]]) -> list[dict[str, str]]:
        return [{"name": name, "version": version} for name, version in sorted(items)]
    unscanned = locked - audited
    installed_not_scanned = installed - audited
    return {
        "classification": "informational per-runner coverage; NOT all-platform clearance",
        "runner_environment": scan.get("environment"),
        "lock_sha256": sbom.get("lock_sha256"),
        "locked_registry_entries": len(locked),
        "audited_locked_entries": len(audited),
        "installed_locked_entries": len(installed),
        "unscanned_locked_variants": pairs(unscanned),
        "installed_not_scanned": pairs(installed_not_scanned),
        "advisory_status": scan["status"],
        "vulnerability_records": scan.get("vulnerability_records"),
        "security_approved": False,
        "licence_policy_approved": False,
    }


def generate(sbom_path: Path, scan_path: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Refusing to replace coverage evidence: {output_dir}")
    report = assess(
        json.loads(sbom_path.read_text(encoding="utf-8")),
        json.loads(scan_path.read_text(encoding="utf-8")),
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "coverage.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = [
        "# AEA package advisory coverage (review only)",
        "",
        f"Locked registry variants: **{report['locked_registry_entries']}**",
        f"Audited at the locked versions: **{report['audited_locked_entries']}**",
        f"Installed on this runner: **{report['installed_locked_entries']}**",
        f"Locked variants not audited here: **{len(report['unscanned_locked_variants'])}**",
        f"Installed variants not audited here: **{len(report['installed_not_scanned'])}**",
        f"Advisory status: **{report['advisory_status']}**",
        "",
        "Missing variants may be unused platform alternatives or dev-only dependencies.",
        "Inspect the JSON identities and the other OS/Python reports before drawing conclusions.",
        "Even a clean report does not certify licences, transitive integrity or production security.",
        "No dependencies are upgraded and no security approval is granted.",
        "",
    ]
    (output_dir / "COVERAGE_REVIEW.md").write_text("\n".join(md), encoding="utf-8")
    print(
        f"PASS: reviewed {report['audited_locked_entries']}/{report['locked_registry_entries']} "
        "locked variants in this runtime selection; gaps retained; no security approval",
        flush=True,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sbom-evidence", required=True, type=Path)
    parser.add_argument("--advisory-evidence", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    generate(args.sbom_evidence, args.advisory_evidence, args.output_dir)


if __name__ == "__main__":
    main()

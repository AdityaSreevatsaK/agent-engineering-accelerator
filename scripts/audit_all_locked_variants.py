"""Audit every version in the immutable lock, including dev-only and OS variants.

Review-only, network-backed advisory evidence. Never installs candidate packages,
updates dependencies, asserts organisational compliance, or grants security approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

if __package__:
    from scripts.audit_public_advisories import checked_run, summarise
else:
    from audit_public_advisories import checked_run, summarise

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "https://pypi.org/simple"
AUDITOR = "pip-audit==2.10.1"


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked_groups(lock_bytes: bytes) -> tuple[list[list[tuple[str, str]]], set[tuple[str, str]]]:
    """Partition duplicate package names into batches accepted by requirements tools."""
    lock = tomllib.loads(lock_bytes.decode("utf-8"))
    packages = lock.get("package")
    if not isinstance(packages, list) or not packages:
        raise ValueError("no locked package entries")
    roots = [item for item in packages if item.get("source") == {"editable": "."}]
    if len(roots) != 1:
        raise ValueError("lock requires exactly one local editable project")
    by_name: dict[str, set[str]] = defaultdict(set)
    for item in packages:
        if item is roots[0]:
            continue
        name = item.get("name")
        version = item.get("version")
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            raise ValueError("invalid locked package identity")
        if item.get("source") != {"registry": REGISTRY}:
            raise ValueError(f"unexpected dependency source: {name}")
        artifacts = ([item["sdist"]] if "sdist" in item else []) + item.get("wheels", [])
        if not artifacts or any(
            not isinstance(artifact, dict)
            or not str(artifact.get("hash", "")).startswith("sha256:")
            for artifact in artifacts
        ):
            raise ValueError(f"missing locked artifact digest: {name}")
        key = canonical(name)
        if version in by_name[key]:
            raise ValueError(f"duplicate locked name/version: {key}=={version}")
        by_name[key].add(version)
    total = {(name, version) for name, versions in by_name.items() for version in versions}
    maximum = max(map(len, by_name.values()))
    groups = [
        [(name, versions[index]) for name, options in sorted(by_name.items())
         if (versions := sorted(options)) and index < len(versions)]
        for index in range(maximum)
    ]
    if not groups or sum(map(len, groups)) != len(total):
        raise ValueError("cannot partition the locked package versions")
    return groups, total


def scan_lock(
    output_dir: Path,
    *,
    lock_path: Path = ROOT / "uv.lock",
    executor=checked_run,
) -> dict[str, Any]:
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Refusing to replace full-lock audit evidence: {output_dir}")
    lock_bytes = lock_path.read_bytes()
    groups, locked = locked_groups(lock_bytes)
    audited: set[tuple[str, str]] = set()
    findings: list[dict[str, Any]] = []
    group_counts: list[dict[str, int]] = []
    with TemporaryDirectory(prefix="aea-complete-lock-advisories-") as temp:
        for index, group in enumerate(groups):
            req = Path(temp) / f"locked-{index}.txt"
            result_path = Path(temp) / f"advisories-{index}.json"
            req.write_text("".join(f"{name}=={version}\n" for name, version in group), encoding="utf-8")
            argv = [
                "uvx", "--python", sys.executable, "--from", AUDITOR, "pip-audit",
                "--requirement", str(req), "--no-deps", "--disable-pip",
                "--format", "json", "--output", str(result_path),
            ]
            process = executor(argv)
            if not result_path.is_file():
                raise RuntimeError(
                    f"auditor did not return usable evidence for lock group {index}: "
                    f"{process.stderr[-1200:] if process.stderr else process.returncode}"
                )
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except (UnicodeError, ValueError) as exc:
                raise RuntimeError(f"unreadable public advisory output for lock group {index}") from exc
            summary = summarise(payload, process.returncode)
            expected = set(group)
            observed = {(item["name"], item["version"]) for item in summary["scanned_packages"]}
            if observed != expected:
                raise ValueError(
                    f"advisory group {index} incomplete or unexpected; "
                    f"missing={sorted(expected - observed)} unexpected={sorted(observed - expected)}"
                )
            if observed & audited:
                raise ValueError("package version was scanned more than once")
            audited |= observed
            findings.extend(summary["findings"])
            group_counts.append({"group": index, "scanned_versions": len(observed)})
    if audited != locked:
        raise ValueError(f"full-lock audit incomplete: {sorted(locked - audited)}")
    findings.sort(key=lambda item: (str(item["package"]), str(item["advisory"])))
    report: dict[str, Any] = {
        "classification": "public advisory lookup of every version in uv.lock; NOT security or licence approval",
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "scanned_at_utc": datetime.now(timezone.utc).isoformat(),
        "auditor": AUDITOR,
        "coverage": "complete_locked_registry_versions",
        "locked_registry_versions": len(locked),
        "audited_registry_versions": len(audited),
        "groups": group_counts,
        "audited_versions": [{"name": name, "version": version} for name, version in sorted(audited)],
        "status": "findings_require_review" if findings else "no_known_findings_in_locked_versions",
        "vulnerability_records": len(findings),
        "findings": findings,
        "security_approved": False,
        "licence_policy_approved": False,
        "limitations": (
            "Public feeds may omit unpublished findings, compromise or malicious behaviour; "
            "audit covers locked names/versions, not platform installation, licence approval, "
            "provider integrations or confidential-data governance."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "full-lock-advisories.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# Complete locked package-version advisory review",
        "",
        f"Date (UTC): {report['scanned_at_utc']}",
        f"Lock SHA-256: `{report['lock_sha256']}`",
        f"Public feed auditor: `{AUDITOR}`",
        f"Versions checked: **{len(audited)}/{len(locked)}**",
        f"Public advisory findings: **{len(findings)}**",
        "",
        "This explicitly includes **development dependencies and alternative Python/OS",
        "versions**, unlike an exported single-runtime selection. It uses the public",
        "advisory feed only and never downloads or executes the candidate packages.",
        "See the JSON file for all package identities and detected advisories.",
        "",
        "**NOT** a security certificate, licence audit, release permission or proof",
        "that unreported vulnerabilities do not exist.",
        "",
    ]
    if findings:
        markdown.extend(["| Package | Advisory | Fixed versions |", "| --- | --- | --- |"])
        for item in findings:
            markdown.append(
                f"| {item['package']}=={item['version']} | {item['advisory']} | "
                f"{', '.join(item['fix_versions']) or 'Not listed'} |"
            )
    (output_dir / "FULL_LOCK_ADVISORY_REVIEW.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )
    print(
        f"FULL-LOCK ADVISORIES: audited {len(audited)}/{len(locked)} versions; "
        f"{len(findings)} public findings; security approval NOT granted",
        flush=True,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="Unused output folder")
    parser.add_argument(
        "--fail-on-findings", action="store_true",
        help="fail the release gate on any published advisory after writing review evidence",
    )
    args = parser.parse_args()
    report = scan_lock(args.output_dir.absolute())
    if args.fail_on_findings and report["vulnerability_records"]:
        parser.exit(1, f"FAIL: {report['vulnerability_records']} public advisory records require remediation\n")


if __name__ == "__main__":
    main()

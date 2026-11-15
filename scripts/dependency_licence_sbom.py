"""Generate a review-only CycloneDX 1.5 BOM and installed licence metadata inventory.

All locked registry package variants are included; packages not installed for the
current Python/platform are explicitly marked, not misrepresented as scanned.
Only installed distribution *metadata* is inspected. No network, code imports,
security decisions, approved licence allowlist or customer information.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def licence_information(meta: Any) -> tuple[list[str], str]:
    expression = meta.get("License-Expression")
    if expression and expression.strip():
        return [expression.strip()], "spdx-expression-in-installed-metadata"
    classifiers = [
        item.removeprefix("License :: ").strip()
        for item in (meta.get_all("Classifier") or [])
        if item.startswith("License :: ")
    ]
    if classifiers:
        return sorted(set(classifiers)), "installed-classifier-not-spdx"
    legacy = (meta.get("License") or "").strip()
    if legacy and "\n" not in legacy and len(legacy) <= 128:
        return [legacy], "legacy-field-not-spdx"
    return [], "not-known-from-installed-metadata"


def build_report(
    lock_bytes: bytes, distributions: list[Any], *, stamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    lock = tomllib.loads(lock_bytes.decode("utf-8"))
    packages = lock.get("package")
    if not isinstance(packages, list) or not packages:
        raise ValueError("missing locked package inventory")
    root = [p for p in packages if p.get("source") == {"editable": "."}]
    if len(root) != 1:
        raise ValueError("expected precisely one local editable AEA root")
    installed: dict[str, Any] = {}
    for dist in distributions:
        name = dist.metadata.get("Name")
        if name:
            installed[normalise(name)] = dist
    components = []
    records = []
    for package in sorted(packages, key=lambda p: (p["name"], p["version"])):
        if package is root[0]:
            continue
        name, version = package["name"], package["version"]
        if package.get("source") != {"registry": "https://pypi.org/simple"}:
            raise ValueError(f"unexpected registry origin: {name}")
        dist = installed.get(normalise(name))
        selected = dist is not None and dist.version == version
        licences, source = licence_information(dist.metadata) if selected else ([], "not-installed-on-this-platform")
        purl = f"pkg:pypi/{normalise(name)}@{version}"
        component: dict[str, Any] = {
            "type": "library", "name": name, "version": version, "purl": purl,
            "bom-ref": purl,
            "properties": [
                {"name": "aea:installed-in-current-ci-environment", "value": str(selected).lower()},
                {"name": "aea:licence-evidence-source", "value": source},
            ],
        }
        if source == "spdx-expression-in-installed-metadata":
            component["licenses"] = [{"expression": licences[0]}]
        elif licences:
            component["licenses"] = [{"license": {"name": item}} for item in licences]
        components.append(component)
        records.append({
            "name": name, "version": version, "installed": selected,
            "licence_evidence": licences, "licence_source": source,
            "installed_version_mismatch": dist.version if dist is not None and not selected else None,
        })
    missing = [r["name"] for r in records if not r["installed"]]
    unknown = [r["name"] for r in records if r["installed"] and not r["licence_evidence"]]
    mismatched = [r["name"] for r in records if r["installed_version_mismatch"]]
    evidence = {
        "classification": "review-only local metadata; NOT approved SBOM, licence audit or security clearance",
        "created_utc": stamp,
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "locked_registry_entries": len(records),
        "installed_locked_entries": len(records) - len(missing),
        "not_installed_here": missing,
        "no_installed_licence_metadata": unknown,
        "version_mismatches": mismatched,
        "licence_policy_approved": False,
        "independent_security_signoff": False,
        "packages": records,
    }
    bom = {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {
            "timestamp": stamp,
            "component": {"type": "application", "name": root[0]["name"], "version": root[0]["version"]},
            "properties": [
                {"name": "aea:status", "value": "unreviewed installed metadata and complete lock variants"},
                {"name": "aea:lock-sha256", "value": evidence["lock_sha256"]},
            ],
        },
        "components": components,
    }
    return evidence, bom


def generate(output: Path, *, lock_path: Path = ROOT / "uv.lock") -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing licence evidence: {output}")
    evidence, bom = build_report(
        lock_path.read_bytes(), list(importlib.metadata.distributions()),
        stamp=datetime.now(timezone.utc).isoformat(),
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "licence-evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (output / "SBOM.cdx.json").write_text(json.dumps(bom, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    lines = [
        "# AEA dependency licences: review-only evidence",
        "",
        f"Locked registry variants: {evidence['locked_registry_entries']}",
        f"Installed on this runner: {evidence['installed_locked_entries']}",
        f"Not selected or absent here: {len(evidence['not_installed_here'])}",
        f"Installed packages with missing licence metadata: {len(evidence['no_installed_licence_metadata'])}",
        f"Installed packages with different versions: {len(evidence['version_mismatches'])}",
        "",
        "These licence strings come from installed package metadata only; classifier names",
        "are not licence-policy approvals. CycloneDX contains ALL locked variants, but",
        "uninstalled variants have no verified installed metadata. This is NOT an approved SBOM.",
        "An authorised security/licence reviewer must check transitive licences, exceptions,",
        "source integrity, platform variants, data policy and permitted use separately.",
        "",
    ]
    (output / "LICENCE_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    if evidence["version_mismatches"]:
        raise RuntimeError("Installed locked dependency versions differ; inspect review artefacts")
    print(
        f"PASS: review-only BOM: {evidence['locked_registry_entries']} locked variants; "
        f"{evidence['installed_locked_entries']} installed; "
        f"{len(evidence['no_installed_licence_metadata'])} unknown licences; "
        "security approval NOT granted",
        flush=True,
    )
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="unused output directory")
    args = parser.parse_args()
    generate(args.output_dir.absolute())


if __name__ == "__main__":
    main()

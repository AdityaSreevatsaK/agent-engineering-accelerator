"""Offline source and hash inventory of the pinned AEA dependency graph.

This is not a vulnerability or licence compliance scan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "https://pypi.org/simple"


def inventory(lock_path: Path, project_path: Path) -> dict[str, object]:
    lock_bytes = lock_path.read_bytes()
    lock = tomllib.loads(lock_bytes.decode("utf-8"))
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    packages = lock.get("package", [])
    if not isinstance(packages, list) or not packages:
        raise ValueError("lockfile contains no packages")
    name = project["project"]["name"]
    version = project["project"]["version"]
    roots = [p for p in packages if p.get("name") == name]
    if len(roots) != 1 or roots[0].get("version") != version or roots[0].get("source") != {"editable": "."}:
        raise ValueError("project metadata differs from the locked editable root")
    root = roots[0]
    invalid_sources: list[str] = []
    missing_hashes: list[str] = []
    for entry in packages:
        if entry is root:
            continue
        package_name = entry.get("name")
        if not isinstance(package_name, str) or not isinstance(entry.get("version"), str):
            raise ValueError("package entry has no valid name or version")
        if entry.get("source") != {"registry": REGISTRY}:
            invalid_sources.append(package_name)
        artifacts = ([entry["sdist"]] if "sdist" in entry else []) + entry.get("wheels", [])
        if not artifacts or any(
            not isinstance(a, dict) or not str(a.get("hash", "")).startswith("sha256:") for a in artifacts
        ):
            missing_hashes.append(package_name)

    direct = [d["name"] for d in root.get("dependencies", [])]
    extras = {k: [d["name"] for d in ds] for k, ds in root.get("optional-dependencies", {}).items()}
    dev = {k: [d["name"] for d in ds] for k, ds in root.get("dev-dependencies", {}).items()}
    names = {p["name"] for p in packages}
    referenced = set(direct) | {d for group in (*extras.values(), *dev.values()) for d in group}
    missing = sorted(referenced - names)
    if missing:
        raise ValueError(f"locked project dependency is missing: {missing}")
    return {
        "classification": "offline source/hash inventory, not vulnerability or licence audit",
        "project": name,
        "version": version,
        "requires_python": project["project"]["requires-python"],
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "locked_entries": len(packages),
        "pypi_registry_entries": len(packages) - 1 - len(invalid_sources),
        "editable_project_entries": 1,
        "direct_runtime": sorted(direct),
        "optional_groups": {k: sorted(v) for k, v in sorted(extras.items())},
        "development_groups": {k: sorted(v) for k, v in sorted(dev.items())},
        "invalid_sources": sorted(invalid_sources),
        "missing_artifact_hashes": sorted(missing_hashes),
        "known_vulnerabilities": None,
        "licences_approved": False,
    }


def validate(result: dict[str, object]) -> None:
    if result["invalid_sources"] or result["missing_artifact_hashes"]:
        raise ValueError("unexpected source or missing artifact hash requires security review")


def write_summary(directory: Path, report: dict[str, object]) -> None:
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(f"Refusing to overwrite inventory: {directory}")
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "inventory.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# AEA locked dependency inventory",
        "",
        f"Project: {report['project']} {report['version']}",
        f"Locked entries: {report['locked_entries']}",
        f"PyPI registry entries: {report['pypi_registry_entries']}",
        f"Editable project entries: {report['editable_project_entries']}",
        f"Unexpected dependency sources: {len(report['invalid_sources'])}",
        f"Artifacts lacking SHA-256: {len(report['missing_artifact_hashes'])}",
        f"Lock SHA-256: {report['lock_sha256']}",
        "",
        "This checks lock provenance and hashes only. CVEs and licences remain unassessed.",
    ]
    (directory / "INVENTORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="Unused directory for a local evidence summary")
    args = parser.parse_args()
    report = inventory(ROOT / "uv.lock", ROOT / "pyproject.toml")
    validate(report)
    if args.output_dir:
        write_summary(args.output_dir.absolute(), report)
    print(
        f"PASS source/hash inventory: {report['locked_entries']} entries, "
        f"{report['pypi_registry_entries']} registry, 1 editable; advisories/licences not assessed",
        flush=True,
    )


if __name__ == "__main__":
    main()

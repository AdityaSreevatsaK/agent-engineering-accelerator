"""Run a dated public Python advisory scan and preserve reviewable results.

The scan is observational, not a release gate or independent security sign-off.
An invalid/incomplete scan fails, rather than implying zero vulnerabilities.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def summarise(payload: dict, returncode: int) -> dict[str, object]:
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("audit result has no dependency inventory")
    findings: list[dict[str, object]] = []
    for package in dependencies:
        if not isinstance(package, dict) or not isinstance(package.get("name"), str):
            raise ValueError("audit returned a malformed package entry")
        vulnerabilities = package.get("vulns", [])
        if not isinstance(vulnerabilities, list):
            raise ValueError("audit returned a malformed vulnerability list")
        for item in vulnerabilities:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError("audit returned a vulnerability without an advisory ID")
            findings.append({
                "package": package["name"],
                "version": package.get("version"),
                "advisory": item["id"],
                "fix_versions": item.get("fix_versions", []),
            })
    if returncode not in (0, 1) or (returncode == 0 and findings) or (returncode == 1 and not findings):
        raise RuntimeError(f"inconsistent/incomplete pip-audit response: exit {returncode}")
    return {
        "status": "findings_require_review" if findings else "no_known_findings_in_scanned_set",
        "scanned_package_entries": len(dependencies),
        "vulnerability_records": len(findings),
        "affected_packages": len({f["package"] for f in findings}),
        "findings": sorted(findings, key=lambda f: (str(f["package"]), str(f["advisory"]))),
        "classification": "dated public advisory lookup, not full security or licence approval",
        "security_approved": False,
    }


def checked_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )


def scan(output_dir: Path) -> dict[str, object]:
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Refusing to replace advisory evidence: {output_dir}")
    with TemporaryDirectory(prefix="aea-security-advisories-") as work:
        requirements = Path(work) / "pinned-runtime.txt"
        result_file = Path(work) / "audit.json"
        exported = checked_run([
            "uv", "export", "--frozen", "--all-extras", "--no-dev",
            "--no-emit-project", "--no-hashes", "--format", "requirements.txt",
            "--output-file", str(requirements),
        ])
        if exported.returncode != 0 or not requirements.is_file():
            raise RuntimeError(f"could not export locked runtime requirements: {exported.stderr[-1200:]}")
        result = checked_run([
            "uvx", "--from", "pip-audit==2.10.1", "pip-audit",
            "--requirement", str(requirements), "--no-deps", "--disable-pip",
            "--format", "json", "--output", str(result_file),
        ])
        if not result_file.is_file():
            raise RuntimeError(
                f"advisory lookup returned no machine-readable result (exit {result.returncode}): "
                f"{result.stderr[-1200:]}"
            )
        try:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("advisory output was unreadable, not a clean scan") from exc
        report = summarise(payload, result.returncode)

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "advisory-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rows = [
        "# AEA public dependency advisory scan",
        "",
        f"Status: **{report['status']}**",
        f"Scanned entries: **{report['scanned_package_entries']}**",
        f"Advisory records: **{report['vulnerability_records']}**",
        f"Affected packages: **{report['affected_packages']}**",
        "",
        "Advisories depend on the public feed and scan date. No automatic fix is applied.",
        "This is not a licence review, malicious-code check, all-platform scan or security sign-off.",
        "",
    ]
    if report["findings"]:
        rows.extend(["| Package | Locked version | Advisory | Published fixes |", "| --- | --- | --- | --- |"])
        for f in report["findings"]:
            rows.append(
                f"| {f['package']} | {f['version']} | {f['advisory']} | "
                f"{', '.join(f['fix_versions']) or 'Not listed'} |"
            )
    else:
        rows.append("No **known** vulnerabilities returned for the scanned dependency set.")
    (output_dir / "ADVISORY_REVIEW.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(
        f"ADVISORY RESULT: {report['status']}; scanned {report['scanned_package_entries']} packages, "
        f"{report['vulnerability_records']} records across {report['affected_packages']} packages "
        "(security approval still required)",
        flush=True,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="Unused output directory for public advisory summary")
    args = parser.parse_args()
    scan(args.output_dir.absolute())


if __name__ == "__main__":
    main()

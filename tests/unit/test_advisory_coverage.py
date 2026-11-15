"""Independent safety tests for per-environment advisory coverage evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import assess_advisory_coverage as coverage

SBOM = {
    "locked_registry_entries": 3,
    "installed_locked_entries": 2,
    "independent_security_signoff": False,
    "lock_sha256": "fake-lock-digest",
    "packages": [
        {"name": "sample-a", "version": "1.0", "installed": True},
        {"name": "sample-b", "version": "2.0", "installed": True},
        {"name": "platform-only", "version": "3.0", "installed": False},
    ],
}
SCAN = {
    "scanned_package_entries": 1,
    "scanned_packages": [{"name": "sample_a", "version": "1.0"}],
    "security_approved": False,
    "status": "no_known_findings_in_scanned_set",
    "vulnerability_records": 0,
    "environment": {"runner_platform": "win32", "python_version": "3.12"},
}


def test_exact_versions_distinguish_scanned_missing_and_installed_missing():
    report = coverage.assess(SBOM, SCAN)
    assert report["locked_registry_entries"] == 3
    assert report["audited_locked_entries"] == 1
    assert report["installed_locked_entries"] == 2
    assert report["unscanned_locked_variants"] == [
        {"name": "platform-only", "version": "3.0"},
        {"name": "sample-b", "version": "2.0"},
    ]
    assert report["installed_not_scanned"] == [{"name": "sample-b", "version": "2.0"}]
    assert report["security_approved"] is False
    assert report["licence_policy_approved"] is False


def test_complete_known_scan_still_does_not_authorise_production():
    scan = {**SCAN, "scanned_package_entries": 3, "scanned_packages": [
        {"name": "sample-a", "version": "1.0"},
        {"name": "sample-b", "version": "2.0"},
        {"name": "platform-only", "version": "3.0"},
    ]}
    report = coverage.assess(SBOM, scan)
    assert not report["unscanned_locked_variants"]
    assert report["security_approved"] is False


@pytest.mark.parametrize("scan_override", [
    {"scanned_packages": []},
    {"scanned_package_entries": 999},
    {"scanned_packages": [{"name": "sample-a", "version": "999"}]},
    {"scanned_packages": [{"name": "sample-a", "version": "1.0"}], "security_approved": True},
    {"status": "unsupported-status"},
    {"scanned_package_entries": 2, "scanned_packages": [
        {"name": "sample_a", "version": "1.0"},
        {"name": "sample-a", "version": "1.0"},
    ]},
])
def test_invalid_incomplete_unlocked_or_approved_scans_fail_closed(scan_override):
    with pytest.raises(ValueError):
        coverage.assess(SBOM, {**SCAN, **scan_override})


def test_missing_installed_status_is_not_accepted():
    bad = {**SBOM, "packages": [dict(item) for item in SBOM["packages"]]}
    del bad["packages"][0]["installed"]
    with pytest.raises(ValueError, match="installed-package"):
        coverage.assess(bad, SCAN)


def test_report_files_are_review_only_and_cannot_overwrite(tmp_path: Path):
    sbom = tmp_path / "licence-evidence.json"
    scan = tmp_path / "advisory-results.json"
    sbom.write_text(json.dumps(SBOM), encoding="utf-8")
    scan.write_text(json.dumps(SCAN), encoding="utf-8")
    target = tmp_path / "new-coverage"
    result = coverage.generate(sbom, scan, target)
    assert json.loads((target / "coverage.json").read_text(encoding="utf-8")) == result
    assert "No dependencies are upgraded" in (target / "COVERAGE_REVIEW.md").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        coverage.generate(sbom, scan, target)

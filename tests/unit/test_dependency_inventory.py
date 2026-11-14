"""Smoke and fail-closed tests for the non-advisory dependency inventory."""
from pathlib import Path

import pytest

from scripts.dependency_inventory import ROOT, inventory, validate, write_summary


def test_actual_lock_contains_only_hasher_verified_pypi_dependencies():
    report = inventory(ROOT / "uv.lock", ROOT / "pyproject.toml")
    validate(report)
    assert report["locked_entries"] >= 2
    assert report["pypi_registry_entries"] == report["locked_entries"] - 1
    assert report["editable_project_entries"] == 1
    assert report["invalid_sources"] == []
    assert report["missing_artifact_hashes"] == []
    assert len(report["lock_sha256"]) == 64
    assert report["known_vulnerabilities"] is None
    assert report["licences_approved"] is False
    assert "inspect-ai" in report["direct_runtime"]


def test_new_summary_is_written_once_and_does_not_claim_vulnerability_clearance(tmp_path: Path):
    report = inventory(ROOT / "uv.lock", ROOT / "pyproject.toml")
    directory = tmp_path / "evidence"
    write_summary(directory, report)
    text = (directory / "INVENTORY.md").read_text(encoding="utf-8")
    assert "CVEs and licences remain unassessed" in text
    assert (directory / "inventory.json").is_file()
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_summary(directory, report)
    assert (directory / "INVENTORY.md").read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    ("lock_source", "expected"),
    [
        ('source = { git = "https://invalid.test/repo" }', "unexpected source"),
        ('source = { registry = "https://untrusted.test/simple" }', "unexpected source"),
    ],
)
def test_nonregistry_sources_are_reported_and_blocked(tmp_path: Path, lock_source: str, expected: str):
    original = (ROOT / "uv.lock").read_text(encoding="utf-8")
    anchor = 'source = { registry = "https://pypi.org/simple" }'
    assert anchor in original
    altered = tmp_path / "uv.lock"
    altered.write_text(original.replace(anchor, lock_source, 1), encoding="utf-8")
    report = inventory(altered, ROOT / "pyproject.toml")
    with pytest.raises(ValueError, match=expected):
        validate(report)


def test_missing_artifact_hash_is_reported_and_blocked(tmp_path: Path):
    original = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'hash = "sha256:' in original
    altered = tmp_path / "uv.lock"
    altered.write_text(original.replace('hash = "sha256:', 'hash = "sha1:', 1), encoding="utf-8")
    report = inventory(altered, ROOT / "pyproject.toml")
    with pytest.raises(ValueError, match="missing artifact hash"):
        validate(report)


def test_root_version_must_match_pyproject(tmp_path: Path):
    original = (ROOT / "uv.lock").read_text(encoding="utf-8")
    altered = tmp_path / "uv.lock"
    altered.write_text(original.replace('version = "2.2.0"', 'version = "0.0.0"', 1), encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        inventory(altered, ROOT / "pyproject.toml")

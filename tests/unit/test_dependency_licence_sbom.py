"""Safety contracts for locked-dependency review BOM and licence metadata."""
from __future__ import annotations

import email
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts import dependency_licence_sbom as sbom


@dataclass
class Dist:
    name: str
    version: str
    licence: str | None = None
    classifiers: tuple[str, ...] = ()

    @property
    def metadata(self):
        result = email.message.Message()
        result["Name"] = self.name
        if self.licence is not None:
            result["License-Expression"] = self.licence
        for classifier in self.classifiers:
            result["Classifier"] = classifier
        return result


LOCK = b'''version = 1
[[package]]
name = "agent-accelerator"
version = "2.2.0"
source = { editable = "." }
[[package]]
name = "sample-a"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "sample-b"
version = "2.0"
source = { registry = "https://pypi.org/simple" }
'''


def test_cyclonedx_contains_both_installed_and_unselected_lock_variants():
    report, bom = sbom.build_report(
        LOCK, [Dist("sample_a", "1.0", "MIT")], stamp="2026-11-15T00:00:00+00:00"
    )
    assert report["locked_registry_entries"] == 2
    assert report["installed_locked_entries"] == 1
    assert report["not_installed_here"] == ["sample-b"]
    assert report["licence_policy_approved"] is False
    assert report["independent_security_signoff"] is False
    assert len(bom["components"]) == 2
    assert bom["components"][0]["licenses"] == [{"expression": "MIT"}]
    assert "licenses" not in bom["components"][1]
    assert bom["components"][1]["properties"][0]["value"] == "false"
    assert report["version_mismatches"] == []
    assert bom["metadata"]["properties"][1]["value"] == report["lock_sha256"]


def test_unknown_or_classifier_licence_is_not_approved():
    report, bom = sbom.build_report(
        LOCK, [
            Dist("sample-a", "1.0"),
            Dist("sample-b", "2.0", classifiers=("License :: OSI Approved :: Apache Software License",)),
        ], stamp="2026-11-15T00:00:00+00:00",
    )
    assert report["no_installed_licence_metadata"] == ["sample-a"]
    assert bom["components"][1]["licenses"] == [
        {"license": {"name": "OSI Approved :: Apache Software License"}}
    ]
    assert report["licence_policy_approved"] is False


def test_wrong_installed_version_is_recorded_not_silently_approved():
    report, bom = sbom.build_report(
        LOCK, [Dist("sample-a", "9.9")], stamp="2026-11-15T00:00:00+00:00"
    )
    assert report["version_mismatches"] == ["sample-a"]
    assert report["installed_locked_entries"] == 0


def test_alternative_version_for_platform_is_not_false_mismatch():
    multi = LOCK + b'''[[package]]
name = "sample-a"
version = "1.1"
source = { registry = "https://pypi.org/simple" }
'''
    report, _ = sbom.build_report(
        multi, [Dist("sample-a", "1.0", "MIT")], stamp="2026-11-15T00:00:00+00:00"
    )
    assert report["locked_registry_entries"] == 3
    assert report["installed_locked_entries"] == 1
    assert report["version_mismatches"] == []
    assert report["not_installed_here"] == ["sample-a", "sample-b"]


def test_unknown_lock_source_rejected():
    bad = LOCK.replace(b"https://pypi.org/simple", b"https://unknown-registry.example")
    with pytest.raises(ValueError, match="unexpected registry origin"):
        sbom.build_report(bad, [], stamp="2026-11-15T00:00:00+00:00")


def test_generator_never_overwrites_existing_evidence(tmp_path: Path):
    location = tmp_path / "evidence"
    location.mkdir()
    marker = location / "do-not-touch.txt"
    marker.write_text("private data", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        sbom.generate(location)
    assert marker.read_text(encoding="utf-8") == "private data"


def test_generator_writes_separate_summary_and_cyclonedx(tmp_path: Path, monkeypatch):
    lock = tmp_path / "uv.lock"
    lock.write_bytes(LOCK)
    monkeypatch.setattr(sbom.importlib.metadata, "distributions", lambda: [Dist("sample-a", "1.0", "MIT")])
    target = tmp_path / "new"
    report = sbom.generate(target, lock_path=lock)
    assert report["licence_policy_approved"] is False
    assert json.loads((target / "licence-evidence.json").read_text(encoding="utf-8")) == report
    assert json.loads((target / "SBOM.cdx.json").read_text(encoding="utf-8"))["bomFormat"] == "CycloneDX"
    assert "NOT an approved SBOM" in (target / "LICENCE_REVIEW.md").read_text(encoding="utf-8")

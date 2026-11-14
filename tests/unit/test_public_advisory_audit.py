"""Contract tests for observational advisory auditing and failed-scan handling."""
import json
import subprocess
from pathlib import Path

import pytest

from scripts import audit_public_advisories as audit


def test_empty_advisories_do_not_claim_security_approval():
    summary = audit.summarise({"dependencies": [{"name": "synthetic", "version": "1.0", "vulns": []}]}, 0)
    assert summary["status"] == "no_known_findings_in_scanned_set"
    assert summary["vulnerability_records"] == 0
    assert summary["security_approved"] is False


def test_findings_are_preserved_and_sorted_for_review():
    payload = {"dependencies": [
        {"name": "synthetic-b", "version": "2.0", "vulns": [{"id": "TEST-2", "fix_versions": []}]},
        {"name": "synthetic-a", "version": "1.0", "vulns": [{"id": "TEST-1", "fix_versions": ["1.1"]}]},
    ]}
    summary = audit.summarise(payload, 1)
    assert summary["status"] == "findings_require_review"
    assert summary["vulnerability_records"] == 2
    assert summary["affected_packages"] == 2
    assert [r["advisory"] for r in summary["findings"]] == ["TEST-1", "TEST-2"]


@pytest.mark.parametrize(
    ("result", "exitcode"),
    [
        ({}, 0),
        ({"dependencies": []}, 1),
        ({"dependencies": [{"name": "x", "vulns": [{"id": "X"}]}]}, 0),
        ({"dependencies": [{"name": "x", "vulns": []}]}, 2),
        ({"dependencies": [{"name": "x", "vulns": "invalid"}]}, 0),
    ],
)
def test_incomplete_scan_never_masquerades_as_vulnerability_free(result, exitcode):
    with pytest.raises((ValueError, RuntimeError)):
        audit.summarise(result, exitcode)


def test_scan_creates_reviewable_output_without_committing_fixes(tmp_path: Path, monkeypatch):
    commands = []

    def fake_call(arguments):
        commands.append(arguments)
        if arguments[1] == "export":
            Path(arguments[-1]).write_text("synthetic==1.0\n", encoding="utf-8")
            return subprocess.CompletedProcess(arguments, 0)
        target = Path(arguments[-1])
        target.write_text(json.dumps({"dependencies": [
            {"name": "synthetic", "version": "1.0", "vulns": [{"id": "TEST-123", "fix_versions": ["1.2"]}]}
        ]}), encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 1)

    monkeypatch.setattr(audit, "checked_run", fake_call)
    target = tmp_path / "advisory-evidence"
    result = audit.scan(target)
    assert result["status"] == "findings_require_review"
    assert json.loads((target / "advisory-results.json").read_text(encoding="utf-8")) == result
    text = (target / "ADVISORY_REVIEW.md").read_text(encoding="utf-8")
    assert "TEST-123" in text
    assert "not a licence" in text
    assert "--no-deps" in commands[1]
    assert "pip-audit==2.10.1" in commands[1]
    assert not any("--fix" in command for command in commands)
    with pytest.raises(FileExistsError):
        audit.scan(target)


def test_network_or_export_failure_does_not_create_clean_report(tmp_path: Path, monkeypatch):
    def failed_export(arguments):
        return subprocess.CompletedProcess(arguments, 2, stderr="synthetic disconnected registry")

    monkeypatch.setattr(audit, "checked_run", failed_export)
    target = tmp_path / "unscanned"
    with pytest.raises(RuntimeError, match="could not export"):
        audit.scan(target)
    assert not target.exists()

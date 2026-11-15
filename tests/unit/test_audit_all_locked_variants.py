"""Offline contract tests for full lock-version public advisory coverage."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import audit_all_locked_variants as audit


def _lock(records: list[tuple[str, str]]) -> bytes:
    text = ['version = 1', '[[package]]', 'name = "agent-accelerator"',
            'version = "2.2.0"', 'source = { editable = "." }']
    for name, version in records:
        text.extend([
            '[[package]]', f'name = "{name}"', f'version = "{version}"',
            'source = { registry = "https://pypi.org/simple" }',
            'sdist = { url = "https://files.pythonhosted.org/synthetic.tar.gz", hash = "sha256:' +
            'a' * 64 + '" }',
        ])
    return ('\n'.join(text) + '\n').encode('utf-8')


LOCK = _lock([
    ("numpy", "2.4.6"), ("numpy", "2.5.4"), ("pytest", "9.2.0"),
    ("langgraph", "1.2.20"),
])


def test_partition_preserves_every_version_without_conflicting_names():
    groups, identities = audit.locked_groups(LOCK)
    assert len(groups) == 2
    assert len(identities) == 4
    assert set(groups[0]) == {
        ("langgraph", "1.2.20"), ("numpy", "2.4.6"), ("pytest", "9.2.0")
    }
    assert groups[1] == [("numpy", "2.5.4")]


def test_all_locked_dev_and_alternative_versions_audited_without_overwrite(tmp_path: Path):
    lock = tmp_path / "uv.lock"
    lock.write_bytes(LOCK)
    calls = []

    def fake_auditor(argv):
        calls.append(argv)
        assert "--no-deps" in argv and "--disable-pip" in argv
        assert "--python" in argv and "--requirement" in argv
        assert "pip-audit==2.10.1" in argv
        contents = Path(argv[argv.index("--requirement") + 1]).read_text(encoding="utf-8")
        entries = [line.strip().split("==") for line in contents.splitlines() if line.strip()]
        assert len(entries) == len({name for name, _ in entries})
        result_file = Path(argv[argv.index("--output") + 1])
        result_file.write_text(json.dumps({"dependencies": [
            {"name": name, "version": version, "vulns": []} for name, version in entries
        ]}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)

    output = tmp_path / "full-audit"
    result = audit.scan_lock(output, lock_path=lock, executor=fake_auditor)
    assert len(calls) == 2
    assert result["locked_registry_versions"] == 4
    assert result["audited_registry_versions"] == 4
    assert result["vulnerability_records"] == 0
    assert result["security_approved"] is False
    assert result["licence_policy_approved"] is False
    assert result["groups"] == [{"group": 0, "scanned_versions": 3},
                                {"group": 1, "scanned_versions": 1}]
    assert json.loads((output / "full-lock-advisories.json").read_text(encoding="utf-8")) == result
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        audit.scan_lock(output, lock_path=lock, executor=fake_auditor)
    assert len(calls) == 2


def test_known_findings_still_preserved_as_review_only(tmp_path: Path):
    lock = tmp_path / "uv.lock"
    lock.write_bytes(_lock([("one", "1.0")]))

    def reporting_auditor(argv):
        Path(argv[-1]).write_text(json.dumps({"dependencies": [
            {"name": "one", "version": "1.0", "vulns": [
                {"id": "TEST-1", "fix_versions": ["1.1"]}]}
        ]}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 1)

    report = audit.scan_lock(tmp_path / "advisory", lock_path=lock, executor=reporting_auditor)
    assert report["status"] == "findings_require_review"
    assert report["vulnerability_records"] == 1
    assert report["findings"][0]["advisory"] == "TEST-1"
    assert report["security_approved"] is False


@pytest.mark.parametrize("broken_audit", ["empty", "missing", "unexpected", "wrong_exit", "invalid_json"])
def test_incomplete_public_scan_fails_without_creating_clean_evidence(tmp_path: Path, broken_audit: str):
    lock = tmp_path / "uv.lock"
    lock.write_bytes(_lock([("one", "1.0")]))

    def fake(argv):
        if broken_audit == "missing":
            return subprocess.CompletedProcess(argv, 2, stderr="network disconnected")
        if broken_audit == "invalid_json":
            Path(argv[-1]).write_text("{", encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0)
        deps = (
            [] if broken_audit == "empty" else
            [{"name": "other", "version": "1.0", "vulns": []}]
            if broken_audit == "unexpected" else
            [{"name": "one", "version": "1.0", "vulns": []}]
        )
        Path(argv[-1]).write_text(json.dumps({"dependencies": deps}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 1 if broken_audit == "wrong_exit" else 0)

    target = tmp_path / "result"
    with pytest.raises((ValueError, RuntimeError)):
        audit.scan_lock(target, lock_path=lock, executor=fake)
    assert not target.exists()


@pytest.mark.parametrize("broken", [
    _lock([("one", "1.0"), ("one", "1.0")]),
    _lock([("one", "1.0")]).replace(b"https://pypi.org/simple", b"https://unknown.example"),
    _lock([("one", "1.0")]).replace(b"sha256:", b"sha1:"),
])
def test_bad_lock_source_hash_or_duplicate_fails_closed(broken: bytes):
    with pytest.raises(ValueError):
        audit.locked_groups(broken)


def test_strict_release_cli_rejects_known_public_findings(tmp_path: Path, monkeypatch):
    import sys
    target = tmp_path / "review"
    monkeypatch.setattr(audit, "scan_lock", lambda path: {"vulnerability_records": 3})
    monkeypatch.setattr(
        sys, "argv",
        ["audit_all_locked_variants.py", "--output-dir", str(target), "--fail-on-findings"],
    )
    with pytest.raises(SystemExit) as exc:
        audit.main()
    assert exc.value.code == 1


def test_observational_cli_does_not_block_manual_security_review(tmp_path: Path, monkeypatch):
    import sys
    target = tmp_path / "review"
    monkeypatch.setattr(audit, "scan_lock", lambda path: {"vulnerability_records": 3})
    monkeypatch.setattr(
        sys, "argv", ["audit_all_locked_variants.py", "--output-dir", str(target)]
    )
    audit.main()

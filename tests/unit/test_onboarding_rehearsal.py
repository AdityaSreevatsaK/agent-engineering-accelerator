"""Tests for scripted onboarding evidence; no providers or real integration invoked."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import onboarding_rehearsal as onboarding
from scripts.conventional_agent_checks import EVIDENCE_PREFIX


def test_refuses_to_touch_existing_operator_directory(tmp_path):
    target = tmp_path / "data"
    target.mkdir()
    marker = target / "notes.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        onboarding.run_onboarding(target, install=False)
    assert marker.read_text(encoding="utf-8") == "keep"


def test_sanitised_environment_masks_provider_tokens(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unapproved-token")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "unapproved-secret")
    env = onboarding.clean_environment()
    assert env["OPENAI_API_KEY"] == ""
    assert env["AWS_SECRET_ACCESS_KEY"] == ""
    assert env["AWS_EC2_METADATA_DISABLED"] == "true"


def test_command_error_does_not_disclose_process_output(monkeypatch, tmp_path):
    def failed_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="confidential input", stderr="private stderr")
    monkeypatch.setattr(onboarding.subprocess, "run", failed_run)
    with pytest.raises(AssertionError) as exc:
        onboarding.measure_command(
            ["python", "bad"], cwd=tmp_path, env={}, expected_code=0, markers=("PASS",)
        )
    assert "confidential" not in str(exc.value)
    assert "private" not in str(exc.value)
    assert "expected=0" in str(exc.value)


def _synthetic_app(tmp_path: Path) -> Path:
    app = tmp_path / "app"
    app.mkdir()
    rows = [
        {"id": "equipment-202" if i == 0 else f"case-{i}", "input": f"question {i}",
         "expected_output": "expected"}
        for i in range(12)
    ]
    (app / "dataset.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
    )
    return app


@pytest.mark.parametrize("fresh_install", [False, True], ids=["installed-python", "fresh-dependency-sync"])
def test_onboarding_rehearsal_records_machine_milestones_not_human_effort(
    tmp_path, monkeypatch, fresh_install
):
    app = _synthetic_app(tmp_path)
    monkeypatch.setattr(onboarding, "SCENARIOS", (("equipment-strands", "strands", app),))
    monkeypatch.setattr(onboarding, "environment_python", lambda root: Path(sys.executable))
    calls: list[list[str]] = []

    def fake_measure(command, *, cwd, env, expected_code, markers=()):
        calls.append(command)
        if command[0] == "uv":
            assert fresh_install
            assert "sync" in command and "--locked" in command
            return subprocess.CompletedProcess(command, 0, stdout=""), 2.75
        if "doctor" in command:
            assert expected_code == 0
            return subprocess.CompletedProcess(command, 0, stdout="PASS: preflight complete"), 0.25
        if "check" in command:
            baseline = Path(command[command.index("--baseline") + 1])
            runs = Path(command[command.index("--runs-dir") + 1])
            runs.mkdir(parents=True, exist_ok=True)
            if "--update-baseline" in command:
                baseline.mkdir(parents=True)
                (baseline / "ref.json").write_text("synthetic", encoding="utf-8")
                (baseline / "report.md").write_text("approved baseline", encoding="utf-8")
                return subprocess.CompletedProcess(
                    command, 0, stdout="passed=12/12\nBASELINE frozen:"
                ), 1.2
            if "agent:build_broken_agent" in command:
                (runs / "comparison.md").write_text(
                    "## Newly failing\n\n- equipment-202 (FAIL): synthetic\n\n## Statistics\n",
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 1, stdout="REGRESSION: baseline"), 1.4
            (runs / "comparison.md").write_text("**OK**", encoding="utf-8")
            return subprocess.CompletedProcess(
                command, 0, stdout="passed=12/12\nOK: baseline"
            ), 0.8
        if "--factory" in command:
            bad = "build_broken_agent" in command
            obj = {
                "case_count": 12, "passing_case_count": 11 if bad else 12,
                "failing_case_ids": ["equipment-202"] if bad else [],
                "passed": not bad,
            }
            return subprocess.CompletedProcess(
                command, int(bad), stdout=EVIDENCE_PREFIX + json.dumps(obj)
            ), 0.3
        raise AssertionError("unexpected subprocess")

    monkeypatch.setattr(onboarding, "measure_command", fake_measure)
    result = onboarding.run_onboarding(tmp_path / "pilot", install=fresh_install)
    assert result["human_first_valid_report_minutes"] is None
    assert result["human_case_authoring_minutes"] is None
    assert result["developer_effort_saved_percent"] is None
    assert result["independent_pilot_teams"] == 0
    assert result["shared_dependency_install_seconds"] == (2.75 if fresh_install else None)
    row = result["scenarios"]["equipment-strands"]
    assert row["doctor_preflight_seconds"] == 0.25
    assert row["aea_first_valid_report_seconds"] == 1.2
    assert row["aea_preflight_plus_first_report_seconds"] == 1.45
    assert row["conventional_first_complete_case_check_seconds"] == 0.3
    assert row["newly_failing_case_ids"] == ["equipment-202"]
    assert row["baseline_integrity_verified"] is True
    assert row["regression_parity"] is True
    assert len(calls) == (7 if fresh_install else 6)
    summary = (tmp_path / "pilot" / onboarding.SUMMARY_NAME).read_text(encoding="utf-8")
    assert "No engineer independently onboarded" in summary
    assert "a like-for-like" in summary
    assert json.loads((tmp_path / "pilot" / onboarding.EVIDENCE_NAME).read_text(encoding="utf-8")) == result


def test_environment_python_requires_real_installed_interpreter(tmp_path):
    with pytest.raises(FileNotFoundError, match="Expected installed project environment"):
        onboarding.environment_python(tmp_path)

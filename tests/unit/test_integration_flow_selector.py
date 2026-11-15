"""Guard the one-command Strands/LangGraph selector used in the quickstart guide."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import validate_independent_integrations as demo


def test_unknown_flow_fails_before_creating_any_output(tmp_path: Path):
    target = tmp_path / "evidence"
    with pytest.raises(ValueError, match="Unknown standalone application"):
        demo.run_validation(target, only="not-an-app")
    assert not target.exists()


def test_single_application_still_runs_every_stage_and_preserves_reference(tmp_path: Path, monkeypatch):
    apps = (
        ("equipment-strands", "strands", tmp_path / "equipment"),
        ("vendor-langgraph", "langgraph", tmp_path / "vendor"),
    )
    monkeypatch.setattr(demo, "SCENARIOS", apps)
    monkeypatch.setattr(demo, "validate_dataset", lambda dataset: 12)
    calls = []

    def synthetic_cli(app, factory, baseline, runs, update):
        calls.append((app, factory))
        runs.mkdir(parents=True)
        if update:
            baseline.mkdir(parents=True)
            (baseline / "log.json").write_text("{}", encoding="utf-8")
            (baseline / "report.md").write_text("synthetic", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout="passed=12/12\nBASELINE frozen:")
        if factory == "build_agent":
            (runs / "comparison.md").write_text("**OK**", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout="passed=12/12\nOK: baseline")
        (runs / "comparison.md").write_text(
            "## Newly failing\n\n- equipment-202: fault", encoding="utf-8"
        )
        return subprocess.CompletedProcess([], 1, stdout="REGRESSION: baseline")

    monkeypatch.setattr(demo, "call_cli", synthetic_cli)
    target = tmp_path / "evidence"
    result = demo.run_validation(target, repeats=2, only="equipment-strands")

    assert len(calls) == 4
    assert {app for app, _ in calls} == {apps[0][2]}
    assert [factory for _, factory in calls] == [
        "build_agent", "build_agent", "build_agent", "build_broken_agent"
    ]
    assert list(result["applications"]) == ["equipment-strands"]
    row = result["applications"]["equipment-strands"]
    assert row["case_count"] == 12
    assert row["unchanged_runs_passed"] == 2
    assert row["deliberate_regression_detected"] is True
    assert row["baseline_unchanged"] is True
    assert json.loads((target / "evidence.json").read_text(encoding="utf-8")) == result


def test_cli_passes_requested_flow_to_runner(tmp_path: Path, monkeypatch):
    called = []

    def recorder(output, repeats=1, only=None):
        called.append((output, repeats, only))

    monkeypatch.setattr(demo, "run_validation", recorder)
    monkeypatch.setattr(
        sys, "argv",
        ["validate_independent_integrations.py", "--only", "vendor-langgraph",
         "--repeats", "2", "--output-dir", str(tmp_path / "fresh")],
    )
    demo.main()
    assert called == [(tmp_path / "fresh", 2, "vendor-langgraph")]

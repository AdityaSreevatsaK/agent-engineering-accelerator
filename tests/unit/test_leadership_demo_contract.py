"""Contract-level checks for the leadership demo's truthful synthetic evidence."""
import json
import subprocess
from pathlib import Path

import pytest

from scripts import leadership_demo as demo


def test_leadership_demo_never_overwrites_an_existing_folder(tmp_path: Path):
    existing = tmp_path / "presentation"
    existing.mkdir()
    (existing / "keep.txt").write_text("operator work", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        demo.run_demo(existing)
    assert (existing / "keep.txt").read_text(encoding="utf-8") == "operator work"


def test_leadership_demo_outputs_verified_structured_evidence(tmp_path: Path, monkeypatch):
    def fake_command(target: str, baseline: Path, runs: Path, *, update: bool):
        runs.mkdir(parents=True, exist_ok=True)
        if update:
            baseline.mkdir()
            (baseline / "one.json").write_text("synthetic baseline", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout="passed=11/11 BASELINE frozen:")
        comparison = runs / "sample" / "comparison.md"
        comparison.parent.mkdir()
        if target == demo.GOOD:
            comparison.write_text("**OK**", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout="passed=11/11 OK: baseline")
        comparison.write_text("## Newly failing\n- refund-policy: incorrect", encoding="utf-8")
        return subprocess.CompletedProcess([], 1, stdout="REGRESSION: baseline")

    def fake_export(command, **kwargs):
        target = Path(command[-1])
        target.write_text("<p>Synthetic report</p>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=target.as_posix())

    monkeypatch.setattr(demo, "command", fake_command)
    monkeypatch.setattr(demo.subprocess, "run", fake_export)

    destination = tmp_path / "new-presentation"
    demo.run_demo(destination)

    evidence = json.loads((destination / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["cases"] == 11
    assert evidence["frozen_baseline_passed"] == evidence["unchanged_run_passed"] == 11
    assert evidence["unchanged_comparison_exit_code"] == 0
    assert evidence["deliberate_regression_exit_code"] == 1
    assert evidence["planted_defect_detected"] is True
    assert evidence["approved_baseline_bytes_unchanged"] is True
    assert evidence["human_effort_minutes"] is None
    assert evidence["independent_teams_adopted"] is None
    assert evidence["provider_cost_usd"] is None
    assert (destination / evidence["regression_report"]).is_file()
    assert (destination / evidence["html_report"]).is_file()
    assert "not customer data" in (destination / "DEMO.md").read_text(encoding="utf-8")
    assert "Machine-readable synthetic evidence" in (destination / "DEMO.md").read_text(encoding="utf-8")

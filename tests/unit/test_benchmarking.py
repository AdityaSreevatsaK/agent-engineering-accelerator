"""Unit contracts for reproducible synthetic AEA runtime measurements."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import benchmark_agent_evaluations as bench


@pytest.mark.parametrize(
    ("samples", "q", "expected"),
    [
        ([1.0], 0.95, 1.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.5, 3.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.95, 5.0),
        ([5.0, 3.0, 2.0, 4.0, 1.0], 0.2, 1.0),
    ],
)
def test_nearest_rank_is_observed_not_extrapolated(samples, q, expected):
    assert bench.percentile_nearest_rank(samples, q) == expected


@pytest.mark.parametrize(
    ("samples", "q"),
    [([], 0.95), ([1.0], 0.0), ([1.0], 1.1), ([float("nan")], 0.95),
     ([float("inf")], 0.95), ([-1.0, 2.0], 0.5)],
)
def test_invalid_sample_statistics_fail_closed(samples, q):
    with pytest.raises(ValueError):
        bench.percentile_nearest_rank(samples, q)


@pytest.mark.parametrize("repeats", [0, -2, 21])
def test_bad_repeat_count_does_not_create_evidence(tmp_path, repeats):
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="between 1 and 20"):
        bench.benchmark(output, repeats)
    assert not output.exists()


def test_existing_output_is_not_overwritten(tmp_path):
    marker = tmp_path / "keep.txt"
    marker.write_text("operator data", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        bench.benchmark(tmp_path, repeats=1)
    assert marker.read_text(encoding="utf-8") == "operator data"


def test_benchmark_reports_observations_without_inventing_staff_savings(tmp_path, monkeypatch):
    apps = (
        ("equipment-strands", "strands", tmp_path / "equipment"),
        ("vendor-langgraph", "langgraph", tmp_path / "vendor"),
    )
    monkeypatch.setattr(bench, "SCENARIOS", apps)
    monkeypatch.setattr(bench, "validate_dataset", lambda path: 12)
    counts: dict[str, int] = {}

    def synthetic_check(app_dir: Path, factory: str, baseline: Path, runs: Path, update: bool):
        name = "equipment-strands" if app_dir == apps[0][2] else "vendor-langgraph"
        counts[name] = counts.get(name, 0) + 1
        runs.mkdir(parents=True)
        if update:
            baseline.mkdir(parents=True)
            (baseline / "synthetic.json").write_text("{}", encoding="utf-8")
            (baseline / "report.md").write_text("synthetic test", encoding="utf-8")
            return subprocess.CompletedProcess(["aea"], 0, stdout="passed=12/12\\nBASELINE frozen:")
        if factory == "build_agent":
            (runs / "comparison.md").write_text("**OK**", encoding="utf-8")
            return subprocess.CompletedProcess(["aea"], 0, stdout="passed=12/12\\nOK: baseline")
        (runs / "comparison.md").write_text(
            f"## Newly failing\\n- {bench.FAULT_CASE[name]}", encoding="utf-8"
        )
        return subprocess.CompletedProcess(["aea"], 1, stdout="REGRESSION: baseline")

    monkeypatch.setattr(bench, "call_cli", synthetic_check)
    out = tmp_path / "benchmark-output"
    result = bench.benchmark(out, repeats=2)

    assert counts == {"equipment-strands": 4, "vendor-langgraph": 4}
    assert result["human_effort_minutes"] is None
    assert result["estimated_time_saved_pct"] is None
    assert result["claimable_independent_team_adoption"] is False
    assert len(result["scenarios"]) == 2
    for row in result["scenarios"].values():
        assert row["synthetic_cases"] == 12
        assert row["unchanged_checks_passed"] == 2
        assert row["controlled_faults_detected"] == row["controlled_faults_injected"] == 1
        assert row["baseline_unchanged"] is True
        assert len(row["unchanged_check_seconds"]) == 2
        assert row["unchanged_p95_nearest_rank_s"] >= row["unchanged_median_s"]
    assert json.loads((out / "evidence.json").read_text(encoding="utf-8")) == result
    report = (out / "BENCHMARK.md").read_text(encoding="utf-8")
    assert "not model speed" in report
    assert "1/1 planted fault detected" in report
    assert "p95" in report

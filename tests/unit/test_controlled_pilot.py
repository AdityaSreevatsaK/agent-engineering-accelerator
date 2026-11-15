"""Contracts for the self-authored conventional-control comparison study."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import controlled_pilot_study as study
from scripts import conventional_agent_checks as control


@pytest.mark.parametrize(
    ("answer", "calls", "expected"),
    [
        ("done", [{"name": "lookup", "arguments": {"id": "x"}}], True),
        ("wrong", [{"name": "lookup", "arguments": {"id": "x"}}], False),
        ("done", [], False),
        ("done", [{"name": "lookup", "arguments": {"id": "wrong"}}], False),
    ],
)
def test_control_checks_same_answer_and_exact_tool_contract(answer, calls, expected):
    case = {
        "expected_output": "done",
        "expected_tool_calls": [{"name": "lookup", "arguments": {"id": "x"}}],
    }
    assert control.check_case(case, answer, calls) is expected


def test_strands_control_calls_fresh_agent_and_reads_native_tool_history():
    calls = []

    class Agent:
        messages = [
            {"content": [{"text": "question"}]},
            {"content": [{"toolUse": {"name": "lookup", "input": {"id": "x"}}}]},
            {"content": [{"toolResult": {"status": "success"}}]},
        ]

        def __call__(self, question):
            calls.append(question)
            return "  done  "

    app = SimpleNamespace(build_agent=lambda: Agent())
    assert control.invoke_strands(app, "build_agent", "q") == (
        "done", [{"name": "lookup", "arguments": {"id": "x"}}]
    )
    assert calls == ["q"]


def test_langgraph_control_uses_application_mappers_not_aea_adapters():
    class Graph:
        def invoke(self, state):
            assert state == {"question": "test"}
            return {"answer": "approved"}

    app = SimpleNamespace(
        build_agent=lambda: Graph(),
        to_request=lambda value: {"question": value},
        read_decision=lambda value: value["answer"],
    )
    assert control.invoke_langgraph(app, "build_agent", "test") == ("approved", [])


def test_control_summary_rejects_missing_output_and_inconsistent_counts():
    result = subprocess.CompletedProcess(["python"], 0, stdout="unexpected text")
    with pytest.raises(AssertionError, match="single summary"):
        study.control_summary(result, expected_code=0, count=12)
    payload = {
        "case_count": 12, "passing_case_count": 11, "failing_case_ids": [], "passed": True,
    }
    result.stdout = control.EVIDENCE_PREFIX + json.dumps(payload)
    with pytest.raises(AssertionError, match="case coverage"):
        study.control_summary(result, expected_code=0, count=12)


def test_report_parser_rejects_unknown_or_extra_failure_ids():
    ids = {"equipment-202", "equipment-204", "equipment-206"}
    report = "## Newly failing\n\n- equipment-202 (FAIL): synthetic\n- equipment-206 (FAIL): synthetic\n\n## Statistics\n"
    assert study.newly_failing_ids(report, ids) == {"equipment-202", "equipment-206"}
    with pytest.raises(AssertionError, match="unknown or repeated"):
        study.newly_failing_ids(report.replace("## Statistics", "- wrong (FAIL)\n\n## Statistics"), ids)
    with pytest.raises(AssertionError, match="no newly-failing"):
        study.newly_failing_ids("**OK**", ids)


@pytest.mark.parametrize("repeats", [0, -1, 11])
def test_bad_repeats_does_not_create_output(tmp_path, repeats):
    out = tmp_path / "evidence"
    with pytest.raises(ValueError, match="between 1 and 10"):
        study.pilot(out, repeats)
    assert not out.exists()


def test_existing_output_is_preserved(tmp_path):
    out = tmp_path / "operator-data"
    out.mkdir()
    marker = out / "keep.txt"
    marker.write_text("do not delete", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        study.pilot(out, repeats=1)
    assert marker.read_text(encoding="utf-8") == "do not delete"


def test_study_captures_case_parity_without_claiming_productivity(tmp_path, monkeypatch):
    app_dir = tmp_path / "sample-app"
    app_dir.mkdir()
    rows = [
        {"id": "equipment-202" if i == 0 else f"case-{i}", "input": f"test {i}", "expected_output": "OK"}
        for i in range(12)
    ]
    (app_dir / "dataset.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(study, "SCENARIOS", (("equipment-strands", "strands", app_dir),))

    def fake_cli(app_dir, factory, baseline, runs, update):
        runs.mkdir(parents=True)
        if update:
            baseline.mkdir(parents=True)
            (baseline / "reference.json").write_text("{}", encoding="utf-8")
            (baseline / "report.md").write_text("fixed", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout="passed=12/12\nBASELINE frozen:")
        if factory == "build_broken_agent":
            (runs / "comparison.md").write_text(
                "## Newly failing\n\n- equipment-202 (FAIL): synthetic\n\n## Statistics\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess([], 1, stdout="REGRESSION: baseline")
        (runs / "comparison.md").write_text("**OK**", encoding="utf-8")
        return subprocess.CompletedProcess([], 0, stdout="passed=12/12\nOK: baseline")

    def fake_control(app_dir, framework, factory):
        failing = ["equipment-202"] if factory == "build_broken_agent" else []
        summary = {
            "case_count": 12, "passing_case_count": 12-len(failing),
            "failing_case_ids": failing, "passed": not failing,
        }
        return subprocess.CompletedProcess(
            [], 1 if failing else 0, stdout=control.EVIDENCE_PREFIX + json.dumps(summary)
        )

    monkeypatch.setattr(study, "call_cli", fake_cli)
    monkeypatch.setattr(study, "call_control", fake_control)
    result = study.pilot(tmp_path / "study-output", repeats=2)
    assert result["human_effort_minutes"] is None
    assert result["time_to_first_report_minutes"] is None
    assert result["staff_productivity_change_percent"] is None
    assert result["claimable_multi_team_adoption"] is False
    measured = result["scenarios"]["equipment-strands"]
    assert measured["successful_unchanged_runs_per_method"] == 2
    assert measured["failing_case_ids"] == ["equipment-202"]
    assert measured["parity_of_detected_defects"] is True
    assert len(measured["aea_unchanged_seconds"]) == len(measured["control_unchanged_seconds"]) == 2
    assert "not" in (tmp_path / "study-output" / "STUDY.md").read_text(encoding="utf-8").lower()
    assert json.loads((tmp_path / "study-output" / "evidence.json").read_text(encoding="utf-8")) == result


def test_study_rejects_disagreement_on_detected_defect_ids(tmp_path, monkeypatch):
    app_dir = tmp_path / "fixture"
    app_dir.mkdir()
    (app_dir / "dataset.jsonl").write_text(
        "".join(json.dumps({"id": "equipment-202" if i == 0 else f"case-{i}",
                           "input": "q", "expected_output": "OK"}) + "\n" for i in range(12)),
        encoding="utf-8",
    )
    monkeypatch.setattr(study, "SCENARIOS", (("equipment-strands", "strands", app_dir),))

    def mock_aea(app, factory, baseline, runs, update):
        runs.mkdir(parents=True)
        if update:
            baseline.mkdir()
            (baseline / "log.json").write_text("{}", encoding="utf-8")
            (baseline / "report.md").write_text("baseline", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout="passed=12/12\nBASELINE frozen:")
        if factory == "build_broken_agent":
            (runs / "comparison.md").write_text(
                "## Newly failing\n\n- equipment-202\n- case-1\n\n## Statistics\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess([], 1, stdout="REGRESSION: baseline")
        (runs / "comparison.md").write_text("**OK**", encoding="utf-8")
        return subprocess.CompletedProcess([], 0, stdout="passed=12/12\nOK: baseline")

    def mock_control(app, framework, factory):
        bad = factory == "build_broken_agent"
        return subprocess.CompletedProcess(
            [], 1 if bad else 0,
            stdout=control.EVIDENCE_PREFIX + json.dumps({
                "case_count": 12, "passing_case_count": 11 if bad else 12,
                "failing_case_ids": ["equipment-202"] if bad else [], "passed": not bad,
            }),
        )

    monkeypatch.setattr(study, "call_cli", mock_aea)
    monkeypatch.setattr(study, "call_control", mock_control)
    with pytest.raises(AssertionError, match="disagreement"):
        study.pilot(tmp_path / "study", repeats=1)

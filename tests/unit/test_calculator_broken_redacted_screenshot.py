"""Read-only parser checks for the screenshot-derived redacted calculator log.

The file deliberately lives in reconstruction_drafts: the three screenshot
captures establish result semantics, not the original fixture bytes.
"""
from pathlib import Path

from inspect_ai.log import read_eval_log

from agent_accelerator.compare import load_results
from reconstruction_tools.verify_broken_redacted_screenshot import validate

ROOT = Path(__file__).parents[2]
CANDIDATE = ROOT / "reconstruction_drafts" / "calculator_broken_redacted_SCREENSHOT_CANDIDATE.json"


def test_screenshot_broken_fixture_passes_source_evidence_validator():
    validate()


def test_screenshot_broken_fixture_is_valid_inspect_eval_log():
    log = read_eval_log(CANDIDATE)
    assert log.status == "success"
    assert len(log.samples or []) == 10
    assert log.eval.metadata["capture_content"] is False
    assert log.results.scores[0].metrics["accuracy"].value == 0.8


def test_screenshot_broken_fixture_loads_in_actual_aea_comparison_engine():
    results = load_results(CANDIDATE)
    assert results.status == "success"
    assert len(results.cases) == 10
    assert results.capture_content is False
    assert results.dataset_sha256 is not None
    assert len(results.dataset_sha256) == 64
    assert {case_id for case_id, case in results.cases.items() if not case.passed} == {
        "subtract", "subtract_large"
    }
    assert all(
        results.cases[case_id].failures and all(results.cases[case_id].failures.values())
        for case_id in ("subtract", "subtract_large")
    )

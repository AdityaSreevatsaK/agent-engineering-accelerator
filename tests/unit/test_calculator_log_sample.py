"""Validate parsing and comparison of a representative offline calculator run log."""
from pathlib import Path

from inspect_ai.log import read_eval_log

from agent_accelerator.compare import load_results

SAMPLE = Path(__file__).parents[1] / "fixtures" / "eval_log_sample.json"


def test_log_sample_is_valid_inspect_json():
    log = read_eval_log(SAMPLE)
    assert log.status == "success"
    assert len(log.samples or []) == 10
    assert log.eval.metadata["capture_content"] is False
    assert log.results.scores[0].metrics["accuracy"].value == 0.8


def test_log_sample_loads_into_comparison_engine():
    run = load_results(SAMPLE)
    assert run.status == "success"
    assert len(run.cases) == 10
    assert run.capture_content is False
    assert run.dataset_sha256 is not None and len(run.dataset_sha256) == 64
    assert {key for key, result in run.cases.items() if not result.passed} == {
        "subtract", "subtract_large"
    }

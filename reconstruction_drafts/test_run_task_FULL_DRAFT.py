import shutil
from pathlib import Path
from types import SimpleNamespace

import fsspec
import pytest

import agent_accelerator.run as run_module
from agent_accelerator.run import build_task, run_task

REPO = Path(__file__).parents[2]
DATASET = REPO / "examples" / "calculator" / "dataset.jsonl"
AGENT = "examples.calculator.agent:build_agent"
FIXTURE = REPO / "tests" / "fixtures" / "calculator_capture_content.json"


@pytest.fixture
def task(monkeypatch):
    # The agent factory is imported from the repo's examples package.
    monkeypatch.syspath_prepend(str(REPO))
    return build_task(DATASET, AGENT, "strands", False)


@pytest.fixture
def eval_calls(monkeypatch, tmp_path):
    log_path = tmp_path / "log.json"
    shutil.copy(FIXTURE, log_path)
    calls = []

    def fake_eval(*args, **kwargs):
        calls.append(kwargs)
        return [SimpleNamespace(location=str(log_path))]

    monkeypatch.setattr(run_module, "eval", fake_eval)
    return calls


@pytest.mark.parametrize("max_samples", [0, -1])
def test_max_samples_below_one_raises_before_eval_runs(task, eval_calls, tmp_path, max_samples):
    with pytest.raises(ValueError):
        run_task(task, tmp_path / "run", capture_content=True, max_samples=max_samples)

    assert eval_calls == []


@pytest.mark.parametrize("max_samples", [3, None])
def test_max_samples_is_passed_to_eval_and_recorded_in_metadata(task, eval_calls, tmp_path, max_samples):
    run_task(task, tmp_path / "run", capture_content=True, max_samples=max_samples)

    [kwargs] = eval_calls
    assert "max_samples" in kwargs
    assert kwargs["max_samples"] == max_samples
    assert "max_samples" in kwargs["metadata"]
    assert kwargs["metadata"]["max_samples"] == max_samples


def test_max_samples_defaults_to_none(task, eval_calls, tmp_path):
    run_task(task, tmp_path / "run", capture_content=True)

    [kwargs] = eval_calls
    assert kwargs["max_samples"] is None
    assert kwargs["metadata"]["max_samples"] is None


INPUT_TEXT = "What is 2 plus 3?"


@pytest.fixture
def logging_eval(monkeypatch):
    """Writes the capture fixture to wherever run_task told Inspect to log, as Inspect would."""
    calls = []

    def fake_eval(*args, **kwargs):
        calls.append(kwargs)
        location = f"{kwargs['log_dir']}/fixture-log.json"
        with fsspec.open(location, "w", encoding="utf-8") as handle:
            handle.write(FIXTURE.read_text(encoding="utf-8"))
        return [SimpleNamespace(location=location)]

    monkeypatch.setattr(run_module, "eval", fake_eval)
    return calls


def run_dir_in(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    return run_dir


def test_without_capture_inspect_logs_to_memory_with_realtime_logging_off(task, logging_eval, tmp_path):
    run_task(task, run_dir_in(tmp_path), capture_content=False)

    [kwargs] = logging_eval
    assert kwargs["log_dir"].startswith("memory://")
    assert kwargs["log_realtime"] is False


def test_without_capture_the_only_log_on_disk_is_the_scrubbed_one_in_the_run_dir(task, logging_eval, tmp_path):
    run_dir = run_dir_in(tmp_path)

    log_path = run_task(task, run_dir, capture_content=False)

    assert list(tmp_path.rglob("*.json")) == [log_path]
    assert log_path.parent == run_dir
    assert INPUT_TEXT not in log_path.read_text(encoding="utf-8")


def test_without_capture_the_memory_log_is_removed_afterwards(task, logging_eval, tmp_path):
    run_task(task, run_dir_in(tmp_path), capture_content=False)

    [kwargs] = logging_eval
    assert not fsspec.filesystem("memory").exists(kwargs["log_dir"])


def test_without_capture_the_memory_log_is_removed_when_scrubbing_raises(task, logging_eval, tmp_path, monkeypatch):
    def failing_scrub(log):
        raise RuntimeError("scrub failed")

    monkeypatch.setattr(run_module, "scrub", failing_scrub)

    with pytest.raises(RuntimeError, match="scrub failed"):
        run_task(task, run_dir_in(tmp_path), capture_content=False)

    [kwargs] = logging_eval
    assert not fsspec.filesystem("memory").exists(kwargs["log_dir"])


def test_with_capture_the_log_is_written_to_the_run_dir_unscrubbed(task, logging_eval, tmp_path):
    run_dir = run_dir_in(tmp_path)

    log_path = run_task(task, run_dir, capture_content=True)

    [kwargs] = logging_eval
    assert kwargs["log_dir"] == run_dir.as_posix()
    assert kwargs["log_realtime"] is True
    assert log_path.parent == run_dir
    assert INPUT_TEXT in log_path.read_text(encoding="utf-8")
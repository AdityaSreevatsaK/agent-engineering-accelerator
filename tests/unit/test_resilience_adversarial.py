"""Deterministic adversarial baseline and corrupted-log tests.

No timing assumptions, paid APIs, user data or destructive cleanup operations.
"""
from __future__ import annotations

import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agent_accelerator import baseline as baseline_api
from agent_accelerator.cli import _validate_baseline_target, main
from agent_accelerator.compare import load_results

SAMPLE = Path(__file__).parents[1] / "fixtures" / "eval_log_sample.json"


def _prepare(tmp_path: Path, label: str) -> tuple[Path, Path]:
    runs = tmp_path / f"runs-{label}"
    run_dir = runs / "one"
    run_dir.mkdir(parents=True)
    shutil.copyfile(SAMPLE, run_dir / "new.json")
    (run_dir / "report.md").write_text(f"source {label}", encoding="utf-8")
    return runs, run_dir


def _baseline(tmp_path: Path) -> Path:
    active = tmp_path / "approved"
    active.mkdir()
    shutil.copyfile(SAMPLE, active / "original.json")
    (active / "report.md").write_text("approved original", encoding="utf-8")
    return active


def _publish(run_dir: Path, dest: Path, root: Path):
    return baseline_api.freeze_run_as_baseline(run_dir, dest, root, False, _validate_baseline_target)


def _assert_no_leftovers(root: Path) -> None:
    assert not list(root.glob(".approved.aea-stage-*"))
    assert not (root / ".approved.aea-update.lock").exists()


def test_genuinely_overlapping_writers_are_serialised_and_reader_remains_safe(tmp_path, monkeypatch):
    root_a, source_a = _prepare(tmp_path, "a")
    root_b, source_b = _prepare(tmp_path, "b")
    active = _baseline(tmp_path)
    before = (active / "original.json").read_bytes()
    writer_in_copy = threading.Event()
    release_writer = threading.Event()
    real_copytree = baseline_api.shutil.copytree

    def hold_first_writer(source, destination, *args, **kwargs):
        if Path(source) == source_a:
            writer_in_copy.set()
            if not release_writer.wait(timeout=15):
                raise RuntimeError("test writer was not released")
        return real_copytree(source, destination, *args, **kwargs)

    monkeypatch.setattr(baseline_api.shutil, "copytree", hold_first_writer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_publish, source_a, active, root_a)
        assert writer_in_copy.wait(timeout=15), "first writer did not reach the staged copy"
        try:
            # While the first update holds the real filesystem lock, readers can
            # still consume the approved baseline and other writers fail closed.
            assert len(load_results(active).cases) > 0
            assert (active / "original.json").read_bytes() == before
            with pytest.raises(ValueError, match="already in progress or lock retained"):
                _publish(source_b, active, root_b)
            assert (active / "original.json").read_bytes() == before
        finally:
            release_writer.set()
        backup = future.result(timeout=15)

    assert backup is not None
    assert (backup / "original.json").read_bytes() == before
    assert (active / "new.json").read_bytes() == SAMPLE.read_bytes()
    assert (active / "report.md").read_text(encoding="utf-8") == "source a"
    assert not (active / "original.json").exists()
    _assert_no_leftovers(tmp_path)


@pytest.mark.parametrize(
    "payload",
    ["not json", "{", "[]", '{"eval":{"run_id":17},"samples":"not samples"}'],
)
def test_corrupted_candidate_log_does_not_replace_valid_baseline(tmp_path, payload):
    root, source = _prepare(tmp_path, "candidate")
    active = _baseline(tmp_path)
    before = (active / "original.json").read_bytes()
    (source / "new.json").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="no valid Inspect eval log"):
        _publish(source, active, root)

    assert (active / "original.json").read_bytes() == before
    assert (active / "report.md").read_text(encoding="utf-8") == "approved original"
    assert not list(tmp_path.glob(".approved.aea-backup-*"))
    _assert_no_leftovers(tmp_path)
    assert (source / "new.json").read_text(encoding="utf-8") == payload


def test_partial_stage_copy_failure_does_not_leave_payload_or_mutate_prior(tmp_path, monkeypatch):
    root, source = _prepare(tmp_path, "candidate")
    active = _baseline(tmp_path)
    before = (active / "original.json").read_bytes()

    def interrupted_copy(source_dir, destination, *args, **kwargs):
        dest = Path(destination)
        dest.mkdir(parents=True)
        (dest / "partial.txt").write_text("synthetic unsafe partial write", encoding="utf-8")
        raise OSError("simulated disk interruption after partial copy")

    monkeypatch.setattr(baseline_api.shutil, "copytree", interrupted_copy)
    with pytest.raises(OSError, match="after partial copy"):
        _publish(source, active, root)
    assert (active / "original.json").read_bytes() == before
    assert (active / "report.md").read_text(encoding="utf-8") == "approved original"
    assert not list(tmp_path.rglob("partial.txt"))
    assert not list(tmp_path.glob(".approved.aea-backup-*"))
    _assert_no_leftovers(tmp_path)


@pytest.mark.parametrize("payload", ["{", "not JSON", "[]"])
def test_corrupted_compare_input_exits_with_error_without_overwriting_report(tmp_path, capsys, payload):
    damaged = tmp_path / "damaged.json"
    damaged.write_text(payload, encoding="utf-8")
    output = tmp_path / "report.md"
    output.write_text("retain operator report", encoding="utf-8")

    code = main(["compare", str(SAMPLE), str(damaged), "--output", str(output)])

    assert code == 2
    assert "error:" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "retain operator report"
    assert damaged.read_text(encoding="utf-8") == payload


def test_multiple_updates_retain_each_prior_baseline_instead_of_purging(tmp_path):
    active = _baseline(tmp_path)
    first_root, first = _prepare(tmp_path, "first")
    second_root, second = _prepare(tmp_path, "second")
    (second / "report.md").write_text("third generation", encoding="utf-8")

    old_backup = _publish(first, active, first_root)
    middle_backup = _publish(second, active, second_root)

    assert old_backup is not None and middle_backup is not None
    assert old_backup != middle_backup
    assert (old_backup / "original.json").read_bytes() == SAMPLE.read_bytes()
    assert (middle_backup / "new.json").read_bytes() == SAMPLE.read_bytes()
    assert (middle_backup / "report.md").read_text(encoding="utf-8") == "source first"
    assert (active / "report.md").read_text(encoding="utf-8") == "third generation"
    assert baseline_api.retained_backup_paths(active) == sorted((old_backup, middle_backup))
    _assert_no_leftovers(tmp_path)

"""Deterministic AEA reader interleavings at the baseline activation boundary.

No sleeps, real customer data, cloud calls, external processes or destructive
operator paths. Readers use the actual public compare data loader.
"""
from __future__ import annotations

import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agent_accelerator import baseline as baseline_api
from agent_accelerator.cli import _validate_baseline_target, main
from agent_accelerator.compare import load_results, resolve_log

SAMPLE = Path(__file__).parents[1] / "fixtures" / "eval_log_sample.json"


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    runs = tmp_path / "runs"
    candidate = runs / "next-run"
    candidate.mkdir(parents=True)
    shutil.copyfile(SAMPLE, candidate / "next.json")
    (candidate / "report.md").write_text("new synthetic", encoding="utf-8")
    current = tmp_path / "approved"
    current.mkdir()
    shutil.copyfile(SAMPLE, current / "previous.json")
    (current / "report.md").write_text("old synthetic", encoding="utf-8")
    return runs, candidate, current


def _publish(runs: Path, candidate: Path, baseline: Path) -> Path | None:
    return baseline_api.freeze_run_as_baseline(
        candidate, baseline, runs, False, _validate_baseline_target
    )


def test_three_independent_readers_and_compare_survive_exact_activation_pause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs, candidate, active = _fixture(tmp_path)
    old_bytes = (active / "previous.json").read_bytes()
    moved = threading.Event()
    release = threading.Event()
    original_rename = Path.rename

    def pause_after_previous_moves(self: Path, target: Path) -> Path:
        if self.name == "next" and Path(target) == active:
            moved.set()
            assert release.wait(timeout=15), "test failed to release the publisher"
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", pause_after_previous_moves)
    with ThreadPoolExecutor(max_workers=5) as pool:
        writer = pool.submit(_publish, runs, candidate, active)
        assert moved.wait(timeout=15), "publisher never entered the missing-path window"
        try:
            assert not active.exists()
            previous = baseline_api.activation_backup_path(active)
            assert previous is not None
            assert (previous / "previous.json").read_bytes() == old_bytes
            readers = [pool.submit(load_results, active) for _ in range(3)]
            for reader in readers:
                result = reader.result(timeout=15)
                assert result.cases
                assert result.log_path.parent == previous
            # This calls the published AEA comparison flow, not just a helper.
            assert main(["compare", str(active), str(SAMPLE)]) == 0
            assert (active.parent / ".approved.aea-reader-backup").is_file()
        finally:
            release.set()
        retained = writer.result(timeout=15)

    assert retained is not None and (retained / "previous.json").read_bytes() == old_bytes
    assert (active / "next.json").read_bytes() == SAMPLE.read_bytes()
    assert load_results(active).log_path == active / "next.json"
    assert not (tmp_path / ".approved.aea-reader-backup").exists()
    assert not (tmp_path / ".approved.aea-update.lock").exists()


def test_corrupted_or_stale_pointer_cannot_redirect_to_untrusted_path(tmp_path: Path) -> None:
    runs, candidate, active = _fixture(tmp_path)
    lock = tmp_path / ".approved.aea-update.lock"
    marker = tmp_path / ".approved.aea-reader-backup"
    active.rename(tmp_path / "unrelated-original")
    marker.write_text("../different-place", encoding="utf-8")
    lock.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid baseline handover pointer"):
        load_results(active)
    marker.write_text(".approved.aea-backup-not-present", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_results(active)
    # The same file must not be used in the absence of the writer's lock.
    lock.unlink()
    with pytest.raises(FileNotFoundError):
        load_results(active)
    assert (tmp_path / "unrelated-original" / "previous.json").is_file()


def test_external_recreated_baseline_is_not_replaced_by_backup_fallback(tmp_path: Path) -> None:
    _, _, active = _fixture(tmp_path)
    moved = tmp_path / ".approved.aea-backup-synthetic"
    moved.mkdir()
    active.rename(moved / "previous")
    (tmp_path / ".approved.aea-update.lock").write_text("", encoding="utf-8")
    (tmp_path / ".approved.aea-reader-backup").write_text(moved.name, encoding="utf-8")
    active.mkdir()
    (active / "operator-notes.txt").write_text("do not read or overwrite", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_results(active)
    assert (active / "operator-notes.txt").read_text(encoding="utf-8") == "do not read or overwrite"


def test_activation_failure_rolls_back_and_removes_reader_pointer(tmp_path: Path, monkeypatch) -> None:
    runs, candidate, active = _fixture(tmp_path)
    original_rename = Path.rename

    def reject_candidate(self: Path, target: Path) -> Path:
        if self.name == "next" and Path(target) == active:
            raise OSError("synthetic activation error")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", reject_candidate)
    with pytest.raises(OSError, match="synthetic activation error"):
        _publish(runs, candidate, active)
    assert (active / "previous.json").is_file()
    assert not (tmp_path / ".approved.aea-reader-backup").exists()
    assert not (tmp_path / ".approved.aea-update.lock").exists()


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_handover_pointer_symlink_is_rejected_when_permitted(tmp_path: Path) -> None:
    _, _, active = _fixture(tmp_path)
    active.rename(tmp_path / "inactive")
    marker = tmp_path / ".approved.aea-reader-backup"
    (tmp_path / ".approved.aea-update.lock").write_text("", encoding="utf-8")
    target = tmp_path / "malicious"
    target.write_text(".approved.aea-backup-synthetic", encoding="utf-8")
    try:
        marker.symlink_to(target)
    except OSError:
        pytest.skip("Creating symlinks requires privileges on this OS")
    with pytest.raises(ValueError, match="symlink"):
        resolve_log(active)

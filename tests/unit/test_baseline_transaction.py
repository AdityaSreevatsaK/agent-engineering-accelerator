"""Guarded baseline publish and rollback tests using redacted local evaluation logs."""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from agent_accelerator.baseline import freeze_run_as_baseline
from agent_accelerator.cli import _validate_baseline_target

SAMPLE = Path(__file__).parents[1] / "fixtures" / "eval_log_sample.json"


def make_run(tmp_path: Path) -> tuple[Path, Path]:
    runs = tmp_path / "runs"
    run_dir = runs / "one"
    run_dir.mkdir(parents=True)
    shutil.copyfile(SAMPLE, run_dir / "new.json")
    (run_dir / "report.md").write_text("new report", encoding="utf-8")
    (run_dir / "traces.jsonl").write_text("", encoding="utf-8")
    return runs, run_dir


def make_previous(path: Path) -> None:
    path.mkdir(parents=True)
    shutil.copyfile(SAMPLE, path / "old.json")
    (path / "report.md").write_text("previous report", encoding="utf-8")


def publish(run_dir: Path, baseline: Path, runs: Path) -> Path | None:
    return freeze_run_as_baseline(
        run_dir, baseline, runs, False, _validate_baseline_target
    )


def test_new_baseline_installs_run_copy_without_backup(tmp_path: Path) -> None:
    runs, new = make_run(tmp_path)
    destination = tmp_path / "frozen" / "baseline"
    assert publish(new, destination, runs) is None
    assert (destination / "new.json").read_bytes() == SAMPLE.read_bytes()
    assert (destination / "report.md").read_text(encoding="utf-8") == "new report"
    assert (new / "new.json").exists()
    assert not list(destination.parent.glob(".baseline.aea-backup-*"))
    assert not (destination.parent / ".baseline.aea-update.lock").exists()


def test_prior_baseline_is_retained_with_its_exact_bytes(tmp_path: Path) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)
    old_log = (dest / "old.json").read_bytes()
    backup = publish(new, dest, runs)
    assert backup is not None
    assert backup.parent.name.startswith(".baseline.aea-backup-")
    assert (backup / "old.json").read_bytes() == old_log
    assert (backup / "report.md").read_text(encoding="utf-8") == "previous report"
    assert (dest / "new.json").is_file()
    assert not (dest / "old.json").exists()
    assert not (tmp_path / ".baseline.aea-update.lock").exists()


def test_empty_existing_baseline_is_supported(tmp_path: Path) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    dest.mkdir()
    backup = publish(new, dest, runs)
    assert backup is not None and backup.is_dir()
    assert list(backup.iterdir()) == []
    assert (dest / "new.json").is_file()


def test_unrelated_file_added_after_run_started_is_never_deleted(tmp_path: Path) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)
    (dest / "notes.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(ValueError, match="unrelated or linked files"):
        publish(new, dest, runs)
    assert (dest / "notes.txt").read_text(encoding="utf-8") == "keep me"
    assert (dest / "old.json").is_file()
    assert not list(tmp_path.glob(".baseline.aea-backup-*"))


def test_invalid_new_run_cannot_replace_existing_baseline(tmp_path: Path) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)
    (new / "unrelated.txt").write_text("no", encoding="utf-8")
    with pytest.raises(ValueError, match="unrelated or linked files"):
        publish(new, dest, runs)
    assert (dest / "old.json").is_file()


def test_other_aea_writer_lock_refuses_update(tmp_path: Path) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)
    lock = tmp_path / ".baseline.aea-update.lock"
    lock.write_text("another writer", encoding="utf-8")
    with pytest.raises(ValueError, match="already in progress or lock retained"):
        publish(new, dest, runs)
    assert (dest / "old.json").is_file()
    assert lock.read_text(encoding="utf-8") == "another writer"


def test_staging_failure_leaves_existing_baseline_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)

    def fail_copy(*args: object, **kwargs: object) -> None:
        raise OSError("simulated disk full")

    monkeypatch.setattr("agent_accelerator.baseline.shutil.copytree", fail_copy)
    with pytest.raises(OSError, match="disk full"):
        publish(new, dest, runs)
    assert (dest / "old.json").is_file()
    assert not list(tmp_path.glob(".baseline.aea-backup-*"))
    assert not list(tmp_path.glob(".baseline.aea-stage-*"))
    assert not (tmp_path / ".baseline.aea-update.lock").exists()


def test_failed_install_restores_prior_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)
    original_rename = Path.rename

    def fail_candidate(self: Path, target: Path) -> Path:
        if self.name == "next" and Path(target) == dest:
            raise OSError("simulated publication failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_candidate)
    with pytest.raises(OSError, match="simulated publication failure"):
        publish(new, dest, runs)
    assert (dest / "old.json").read_bytes() == SAMPLE.read_bytes()
    assert (dest / "report.md").read_text(encoding="utf-8") == "previous report"
    assert not (tmp_path / ".baseline.aea-update.lock").exists()


def test_external_recreation_does_not_overwrite_or_discard_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)
    original_rename = Path.rename

    def recreate_target(self: Path, target: Path) -> Path:
        result = original_rename(self, target)
        if self == dest and Path(target).name == "previous":
            dest.mkdir()
            (dest / "someone-elses-notes.txt").write_text("new data", encoding="utf-8")
        return result

    monkeypatch.setattr(Path, "rename", recreate_target)
    with pytest.raises(FileExistsError, match="reappeared"):
        publish(new, dest, runs)
    assert (dest / "someone-elses-notes.txt").read_text(encoding="utf-8") == "new data"
    previous = list(tmp_path.glob(".baseline.aea-backup-*/previous"))
    assert len(previous) == 1 and (previous[0] / "old.json").is_file()


def test_capture_content_is_rejected_without_writing(tmp_path: Path) -> None:
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    with pytest.raises(ValueError, match="capture-content"):
        freeze_run_as_baseline(new, dest, runs, True, _validate_baseline_target)
    assert not dest.exists()


def test_failed_prior_snapshot_move_preserves_original_and_cleans_empty_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed rename must not manufacture a misleading empty backup."""
    runs, new = make_run(tmp_path)
    dest = tmp_path / "baseline"
    make_previous(dest)
    original = (dest / "old.json").read_bytes()
    original_rename = Path.rename

    def fail_old_move(self: Path, target: Path) -> Path:
        if self == dest and Path(target).name == "previous":
            raise OSError("synthetic failure moving previous baseline")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_old_move)
    with pytest.raises(OSError, match="synthetic failure moving"):
        publish(new, dest, runs)

    assert (dest / "old.json").read_bytes() == original
    assert (dest / "report.md").read_text(encoding="utf-8") == "previous report"
    assert not list(tmp_path.glob(".baseline.aea-backup-*"))
    assert not list(tmp_path.glob(".baseline.aea-stage-*"))
    assert not (tmp_path / ".baseline.aea-update.lock").exists()

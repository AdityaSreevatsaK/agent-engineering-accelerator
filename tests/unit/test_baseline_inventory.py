"""Retention discovery and secure baseline copy behaviour, without deletion."""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest

from agent_accelerator.baseline import freeze_run_as_baseline, retained_backup_paths
from agent_accelerator.cli import _validate_baseline_target, main

SAMPLE = Path(__file__).parents[1] / "fixtures" / "eval_log_sample.json"


def fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    runs = tmp_path / "runs"
    fresh = runs / "source"
    fresh.mkdir(parents=True)
    shutil.copyfile(SAMPLE, fresh / "new.json")
    (fresh / "report.md").write_text("new", encoding="utf-8")
    current = tmp_path / "approved"
    current.mkdir()
    shutil.copyfile(SAMPLE, current / "old.json")
    (current / "report.md").write_text("old", encoding="utf-8")
    return runs, fresh, current


def publish(runs: Path, fresh: Path, current: Path) -> Path | None:
    return freeze_run_as_baseline(fresh, current, runs, False, _validate_baseline_target)


def test_retained_backup_inventory_is_read_only_and_matches_saved_previous(tmp_path: Path, capsys):
    runs, fresh, current = fixture_paths(tmp_path)
    previous = publish(runs, fresh, current)
    assert previous is not None
    prior_bytes = (previous / "old.json").read_bytes()
    new_bytes = (current / "new.json").read_bytes()

    assert retained_backup_paths(current) == [previous]
    assert main(["backups", str(current)]) == 0
    stdout = capsys.readouterr().out
    assert previous.as_posix() in stdout
    assert "Nothing was removed" in stdout
    assert (previous / "old.json").read_bytes() == prior_bytes
    assert (current / "new.json").read_bytes() == new_bytes


def test_inventory_with_no_backup_has_clear_output(tmp_path: Path, capsys):
    target = tmp_path / "unpublished"
    assert retained_backup_paths(target) == []
    assert main(["backups", str(target)]) == 0
    assert "No retained AEA baseline backups found" in capsys.readouterr().out


def test_inventory_ignores_nonmatching_and_incomplete_backup_containers(tmp_path: Path):
    current = tmp_path / "approved"
    (tmp_path / ".approved.aea-backup-incomplete").mkdir()
    unrelated = tmp_path / ".other.aea-backup-100"
    (unrelated / "previous").mkdir(parents=True)
    assert retained_backup_paths(current) == []
    assert (unrelated / "previous").is_dir()


def test_inventory_refuses_symlinked_backup_container(tmp_path: Path):
    target = tmp_path / "approved"
    actual = tmp_path / "elsewhere"
    (actual / "previous").mkdir(parents=True)
    alias = tmp_path / ".approved.aea-backup-linked"
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")
    with pytest.raises(ValueError, match="symlink"):
        retained_backup_paths(target)
    assert (actual / "previous").is_dir()


@pytest.mark.skipif(os.name == "nt", reason="Windows access controls require approved ACL policy")
def test_new_baseline_has_private_posix_permissions_without_modifying_source(tmp_path: Path):
    runs, fresh, current = fixture_paths(tmp_path)
    fresh.chmod(0o755)
    (fresh / "new.json").chmod(0o644)
    previous = publish(runs, fresh, current)
    assert previous is not None
    assert stat.S_IMODE(current.stat().st_mode) == 0o700
    assert stat.S_IMODE((current / "new.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((current / "report.md").stat().st_mode) == 0o600
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o755
    assert stat.S_IMODE((fresh / "new.json").stat().st_mode) == 0o644
    assert stat.S_IMODE(previous.parent.stat().st_mode) == 0o700


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission enforcement test")
def test_permission_failure_does_not_replace_previous_baseline(tmp_path: Path, monkeypatch):
    runs, fresh, current = fixture_paths(tmp_path)
    original = Path.chmod

    def fail_on_staged_root(path: Path, mode: int) -> None:
        if path.name == "next" and mode == 0o700:
            raise OSError("simulated mode failure")
        original(path, mode)

    monkeypatch.setattr(Path, "chmod", fail_on_staged_root)
    with pytest.raises(OSError, match="simulated mode failure"):
        publish(runs, fresh, current)

    assert (current / "old.json").read_bytes() == SAMPLE.read_bytes()
    assert not list(tmp_path.glob(".approved.aea-backup-*"))
    assert not list(tmp_path.glob(".approved.aea-stage-*"))
    assert not (tmp_path / ".approved.aea-update.lock").exists()

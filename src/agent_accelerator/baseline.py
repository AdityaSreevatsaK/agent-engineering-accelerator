"""Publish a validated evaluation run as a baseline without deleting earlier versions.

A cooperative lock prevents concurrent AEA updates. Existing baseline directories
are moved to unique backup folders and retained. Recovery is attempted if installing
the new baseline fails, so a filesystem error cannot silently destroy the previous
evaluation. Arbitrary external processes are not controlled by the lock.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

BaselineValidator = Callable[[Path, Path, bool], None]


def retained_backup_paths(baseline: Path) -> list[Path]:
    """Read-only inventory of previous AEA baselines; never follows symlinks or deletes files.

    An incomplete or unexpected backup folder is left untouched for review.
    Only directories containing a real "previous" folder are reported.
    """
    if any(path.is_symlink() for path in (baseline, *baseline.parents)):
        raise ValueError(f"baseline path traverses a symlink: {baseline}")
    parent = baseline.parent
    if not parent.is_dir():
        return []
    prefix = f".{baseline.name}.aea-backup-"
    found: list[Path] = []
    for candidate in parent.iterdir():
        if not candidate.name.startswith(prefix):
            continue
        if candidate.is_symlink():
            raise ValueError(f"backup directory is a symlink; refusing to inspect it: {candidate}")
        if not candidate.is_dir():
            continue
        previous = candidate / "previous"
        if previous.is_symlink():
            raise ValueError(f"prior baseline is a symlink; refusing to inspect it: {previous}")
        if previous.is_dir():
            found.append(previous)
    return sorted(found)


def _private_staged_files(root: Path) -> None:
    """Restrict new baseline file permissions on POSIX; Windows needs reviewed ACLs."""
    if os.name == "nt":
        return
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise ValueError(f"staged baseline contains a linked path: {entry}")
        entry.chmod(0o700 if entry.is_dir() else 0o600)
    root.chmod(0o700)


@contextmanager
def _update_lock(target: Path) -> Iterator[None]:
    """Fail closed if another writer has reserved this baseline.

    Locks are not automatically broken, including after an interrupted process.
    The operator can inspect and remove a stale lock manually when no writer runs.
    """
    lock = target.with_name(f".{target.name}.aea-update.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(f"baseline update already in progress or lock retained at {lock}") from None
    stat = os.fstat(fd)
    try:
        yield
    finally:
        os.close(fd)
        try:
            current = os.lstat(lock)
        except FileNotFoundError:
            raise RuntimeError(f"baseline update lock disappeared: {lock}") from None
        if (stat.st_ino, stat.st_dev) != (current.st_ino, current.st_dev):
            raise RuntimeError(f"baseline update lock changed; refusing to remove {lock}")
        lock.unlink()


def freeze_run_as_baseline(
    run_dir: Path,
    baseline: Path,
    runs_dir: Path,
    capture_content: bool,
    validate: BaselineValidator,
) -> Path | None:
    """Install a redacted run, retaining any existing baseline in a unique backup.

    The active baseline may be briefly unavailable during the directory switch.
    If a competing non-cooperating writer recreates the active target, installation
    fails without deleting either the previous backup or the new content.
    """
    validate(baseline, runs_dir, capture_content)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    with _update_lock(baseline):
        # Recheck after the agent run and after obtaining the cooperative lock.
        validate(baseline, runs_dir, capture_content)
        validate(run_dir, runs_dir, capture_content)
        with tempfile.TemporaryDirectory(
            prefix=f".{baseline.name}.aea-stage-", dir=baseline.parent
        ) as workspace:
            staged = Path(workspace) / "next"
            shutil.copytree(run_dir, staged)
            validate(staged, runs_dir, capture_content)
            # Source run folders can be world-readable under a permissive umask.
            # Before promotion, lock down the new snapshot without touching the source.
            _private_staged_files(staged)
            previous: Path | None = None
            backup_root: Path | None = None
            if baseline.exists():
                backup_root = Path(
                    tempfile.mkdtemp(prefix=f".{baseline.name}.aea-backup-", dir=baseline.parent)
                )
                previous = backup_root / "previous"
                baseline.rename(previous)
            try:
                if baseline.exists() or baseline.is_symlink():
                    raise FileExistsError(f"baseline path reappeared during update: {baseline}")
                staged.rename(baseline)
            except BaseException:
                if previous is not None and not baseline.exists() and not baseline.is_symlink():
                    try:
                        previous.rename(baseline)
                    except OSError as exc:
                        raise RuntimeError(
                            f"baseline activation failed; previous version is safe at {previous}"
                        ) from exc
                if backup_root is not None and previous is not None and not previous.exists():
                    # Only remove an empty backup container; never its contents.
                    try:
                        backup_root.rmdir()
                    except OSError:
                        pass
                raise
            return previous

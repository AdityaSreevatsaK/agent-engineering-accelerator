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


def activation_backup_path(baseline: Path) -> Path | None:
    """Resolve the retained prior snapshot *only* during an AEA baseline handover.

    A reader never guesses which of several earlier backups is the current
    handover snapshot. A pending pointer is written before the old active
    directory is moved. The owning writer removes it after publication/rollback.
    A killed writer leaves the pointer and exclusive update lock for operator
    investigation. This is a read-only fallback, never an automatic recovery.
    """
    if any(path.is_symlink() for path in (baseline, *baseline.parents)):
        raise ValueError(f"baseline path traverses a symlink: {baseline}")
    marker = baseline.with_name(f".{baseline.name}.aea-reader-backup")
    lock = baseline.with_name(f".{baseline.name}.aea-update.lock")
    if not lock.is_file():
        return None
    if marker.is_symlink():
        raise ValueError(f"baseline reader pointer is a symlink: {marker}")
    if not marker.is_file():
        return None
    backup_name = marker.read_text(encoding="utf-8").strip()
    prefix = f".{baseline.name}.aea-backup-"
    if not backup_name.startswith(prefix) or Path(backup_name).name != backup_name:
        raise ValueError(f"invalid baseline handover pointer at {marker}")
    root = baseline.parent / backup_name
    previous = root / "previous"
    if root.is_symlink() or previous.is_symlink():
        raise ValueError(f"linked baseline backup is unsafe: {root}")
    return previous if previous.is_dir() else None


def _write_reader_pointer(baseline: Path, backup_root: Path) -> tuple[Path, tuple[int, int]]:
    """Create a private, exclusive handover marker before moving the active directory."""
    marker = baseline.with_name(f".{baseline.name}.aea-reader-backup")
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        token = (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
        os.write(fd, backup_root.name.encode("utf-8"))
    finally:
        os.close(fd)
    return marker, token


def _unlink_owned_reader_pointer(marker: Path, token: tuple[int, int]) -> None:
    """Never delete a marker replaced by a different process."""
    current = marker.lstat()
    if marker.is_symlink() or (current.st_dev, current.st_ino) != token:
        raise RuntimeError(f"baseline reader pointer changed; refusing to remove {marker}")
    marker.unlink()


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
            marker: Path | None = None
            marker_token: tuple[int, int] | None = None
            try:
                if baseline.exists():
                    backup_root = Path(
                        tempfile.mkdtemp(prefix=f".{baseline.name}.aea-backup-", dir=baseline.parent)
                    )
                    previous = backup_root / "previous"
                    # The retained snapshot is discoverable by cooperating readers
                    # even when the active path disappears between two renames.
                    marker, marker_token = _write_reader_pointer(baseline, backup_root)
                    baseline.rename(previous)
                if baseline.exists() or baseline.is_symlink():
                    raise FileExistsError(f"baseline path reappeared during update: {baseline}")
                staged.rename(baseline)
            except BaseException:
                if previous is not None and previous.exists() and not baseline.exists() and not baseline.is_symlink():
                    try:
                        previous.rename(baseline)
                    except OSError as exc:
                        raise RuntimeError(
                            f"baseline activation failed; previous version is safe at {previous}"
                        ) from exc
                if backup_root is not None and previous is not None and not previous.exists():
                    try:
                        backup_root.rmdir()
                    except OSError:
                        pass
                raise
            finally:
                if marker is not None and marker_token is not None:
                    _unlink_owned_reader_pointer(marker, marker_token)
            return previous

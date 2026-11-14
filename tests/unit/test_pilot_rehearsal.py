"""Local pilot-rehearsal argument and output safety contracts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import pilot_rehearsal


def test_main_passes_cli_repeat_count_to_rehearsal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: list[tuple[Path, int]] = []

    def recorder(output: Path, repeats: int = 3) -> None:
        seen.append((output, repeats))

    monkeypatch.setattr(pilot_rehearsal, "run_rehearsal", recorder)
    target = tmp_path / "new-pilot"
    monkeypatch.setattr(
        sys, "argv", ["pilot_rehearsal.py", "--output-dir", str(target), "--repeats", "1"]
    )

    pilot_rehearsal.main()

    assert seen == [(target, 1)]


@pytest.mark.parametrize("repeats", [0, -2])
def test_rehearsal_rejects_nonpositive_repeat_counts(tmp_path: Path, repeats: int) -> None:
    target = tmp_path / "unused"
    with pytest.raises(ValueError, match="at least 1"):
        pilot_rehearsal.run_rehearsal(target, repeats=repeats)
    assert not target.exists()


def test_rehearsal_refuses_to_replace_existing_output(tmp_path: Path) -> None:
    original = tmp_path / "important.txt"
    original.write_text("retain me", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        pilot_rehearsal.run_rehearsal(tmp_path, repeats=1)

    assert original.read_text(encoding="utf-8") == "retain me"

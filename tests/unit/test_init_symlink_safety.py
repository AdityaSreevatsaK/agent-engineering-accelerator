"""New security-hardening tests, distinct from historical v2.2.0 source tests.

The --force scaffolder must not follow symlinks to outside the target folder.
Windows setups without symlink privileges skip only the symlink-specific cases.
"""

from pathlib import Path

import pytest

from agent_accelerator.cli import EXIT_ERROR, main


def link_or_skip(link: Path, destination: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(destination, target_is_directory=directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Local filesystem cannot create symlinks: {exc}")


def test_init_force_never_truncates_external_file_via_agent_symlink(tmp_path, capsys):
    target = tmp_path / "bot"
    target.mkdir()
    outside = tmp_path / "outside-agent.py"
    outside.write_text("DO NOT ALTER AGENT\n", encoding="utf-8")
    link_or_skip(target / "agent.py", outside)
    dataset = target / "dataset.jsonl"
    dataset.write_text("DO NOT ALTER DATASET\n", encoding="utf-8")

    assert main(["init", str(target), "--force"]) == EXIT_ERROR
    assert "linked template" in capsys.readouterr().err
    assert outside.read_text(encoding="utf-8") == "DO NOT ALTER AGENT\n"
    assert dataset.read_text(encoding="utf-8") == "DO NOT ALTER DATASET\n"
    assert (target / "agent.py").is_symlink()


def test_init_force_checks_dataset_symlink_before_editing_normal_agent(tmp_path, capsys):
    target = tmp_path / "bot"
    target.mkdir()
    agent = target / "agent.py"
    agent.write_text("DO NOT ALTER AGENT\n", encoding="utf-8")
    outside = tmp_path / "outside-dataset.jsonl"
    outside.write_text("DO NOT ALTER DATASET\n", encoding="utf-8")
    link_or_skip(target / "dataset.jsonl", outside)

    assert main(["init", str(target), "--force"]) == EXIT_ERROR
    assert "linked template" in capsys.readouterr().err
    assert agent.read_text(encoding="utf-8") == "DO NOT ALTER AGENT\n"
    assert outside.read_text(encoding="utf-8") == "DO NOT ALTER DATASET\n"


def test_init_force_rejects_link_to_existing_target_directory(tmp_path, capsys):
    real = tmp_path / "real-bot"
    real.mkdir()
    agent = real / "agent.py"
    agent.write_text("DO NOT ALTER\n", encoding="utf-8")
    alias = tmp_path / "alias-bot"
    link_or_skip(alias, real, directory=True)

    assert main(["init", str(alias), "--force"]) == EXIT_ERROR
    assert "symlink" in capsys.readouterr().err
    assert alias.is_symlink()
    assert agent.read_text(encoding="utf-8") == "DO NOT ALTER\n"
    assert not (real / "dataset.jsonl").exists()


@pytest.mark.parametrize("force", [False, True])
def test_init_does_not_create_files_through_linked_parent(tmp_path, capsys, force):
    outside = tmp_path / "outside-parent"
    outside.mkdir()
    alias = tmp_path / "alias"
    link_or_skip(alias, outside, directory=True)
    child = alias / "not-yet-created"

    assert main(["init", str(child), *(["--force"] if force else [])]) == EXIT_ERROR
    assert "symlink" in capsys.readouterr().err
    assert not (outside / "not-yet-created").exists()


def test_init_force_still_overwrites_existing_regular_files(tmp_path):
    """The documented normal --force behaviour must remain unchanged."""
    target = tmp_path / "bot"
    target.mkdir()
    (target / "agent.py").write_text("old agent\n", encoding="utf-8")
    (target / "dataset.jsonl").write_text("old dataset\n", encoding="utf-8")
    untouched = target / "notes.txt"
    untouched.write_text("retain me\n", encoding="utf-8")

    assert main(["init", str(target), "--force"]) == 0
    assert "old agent" not in (target / "agent.py").read_text(encoding="utf-8")
    assert "old dataset" not in (target / "dataset.jsonl").read_text(encoding="utf-8")
    assert untouched.read_text(encoding="utf-8") == "retain me\n"

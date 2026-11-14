"""Validate safe baseline-directory replacement with a local Inspect log fixture."""

import shutil
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log, write_eval_log
from inspect_ai.model import ChatMessageUser

from agent_accelerator.cli import _validate_baseline_target

ROOT = Path(__file__).parents[2]
VALID_EVAL = ROOT / "tests" / "fixtures" / "eval_log_sample.json"


def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "unrelated-runs"


def baseline_with_real_inspect_log(tmp_path: Path) -> Path:
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    shutil.copyfile(VALID_EVAL, baseline / "old.json")
    return baseline


def link_or_skip(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable on this runner: {exc}")


def test_baseline_freeze_allows_normal_run_folder_with_expected_files(tmp_path):
    baseline = baseline_with_real_inspect_log(tmp_path)
    (baseline / "report.md").write_text("old report\n", encoding="utf-8")
    (baseline / "comparison.md").write_text("old comparison\n", encoding="utf-8")
    (baseline / "traces.jsonl").write_text("", encoding="utf-8")

    _validate_baseline_target(baseline, run_dir(tmp_path), False)
    assert (baseline / "old.json").is_file()


@pytest.mark.parametrize("kind", ["nonexistent", "empty"])
def test_baseline_freeze_allows_new_or_empty_directory(tmp_path, kind):
    baseline = tmp_path / "baseline"
    if kind == "empty":
        baseline.mkdir()
    _validate_baseline_target(baseline, run_dir(tmp_path), False)


@pytest.mark.parametrize("content", ['{"unrelated": true}', '{}', 'not a JSON document'])
def test_baseline_freeze_refuses_single_json_that_is_not_a_valid_inspect_log(tmp_path, content):
    baseline = tmp_path / "important-files"
    baseline.mkdir()
    (baseline / "only.json").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="no valid Inspect eval log"):
        _validate_baseline_target(baseline, run_dir(tmp_path), False)
    assert (baseline / "only.json").read_text(encoding="utf-8") == content


@pytest.mark.parametrize("extra", ["notes.txt", "nested", "report.html"])
def test_baseline_freeze_refuses_unrelated_files_even_with_one_valid_log(tmp_path, extra):
    baseline = baseline_with_real_inspect_log(tmp_path)
    other = baseline / extra
    if extra == "nested":
        other.mkdir()
        (other / "private.txt").write_text("DO NOT DELETE\n", encoding="utf-8")
    else:
        other.write_text("DO NOT DELETE\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unrelated or linked files"):
        _validate_baseline_target(baseline, run_dir(tmp_path), False)
    assert (baseline / "old.json").is_file()
    assert other.exists()


def test_baseline_freeze_refuses_symlinked_log_even_if_it_resolves_to_valid_inspect_json(tmp_path):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    external = tmp_path / "external.json"
    shutil.copyfile(VALID_EVAL, external)
    link_or_skip(baseline / "old.json", external)

    with pytest.raises(ValueError, match="unrelated or linked files"):
        _validate_baseline_target(baseline, run_dir(tmp_path), False)
    assert external.read_bytes() == VALID_EVAL.read_bytes()


def test_baseline_freeze_refuses_symlinked_directory(tmp_path):
    original = baseline_with_real_inspect_log(tmp_path)
    alias = tmp_path / "linked-baseline"
    link_or_skip(alias, original, directory=True)

    with pytest.raises(ValueError, match="symlink"):
        _validate_baseline_target(alias, run_dir(tmp_path), False)
    assert (original / "old.json").is_file()


def test_baseline_freeze_refuses_symlinked_parent_directory(tmp_path):
    actual_parent = tmp_path / "actual-parent"
    actual_parent.mkdir()
    alias_parent = tmp_path / "linked-parent"
    link_or_skip(alias_parent, actual_parent, directory=True)
    target = alias_parent / "baseline"

    with pytest.raises(ValueError, match="symlink"):
        _validate_baseline_target(target, run_dir(tmp_path), False)
    assert not (actual_parent / "baseline").exists()


def test_baseline_freeze_still_refuses_recursive_runs_folder(tmp_path):
    baseline = baseline_with_real_inspect_log(tmp_path)
    with pytest.raises(ValueError, match="contains --runs-dir"):
        _validate_baseline_target(baseline, baseline / "runs", False)


def test_baseline_freeze_still_refuses_capture_content(tmp_path):
    baseline = tmp_path / "baseline"
    with pytest.raises(ValueError, match="--capture-content"):
        _validate_baseline_target(baseline, run_dir(tmp_path), True)


def test_baseline_freeze_refuses_explicitly_captured_log(tmp_path):
    baseline = baseline_with_real_inspect_log(tmp_path)
    file = baseline / "old.json"
    log = read_eval_log(file)
    log.eval.metadata = {**(log.eval.metadata or {}), "capture_content": True}
    write_eval_log(log, location=file)

    with pytest.raises(ValueError, match="records captured content"):
        _validate_baseline_target(baseline, run_dir(tmp_path), False)
    assert file.is_file()


@pytest.mark.parametrize("field", ["input", "target", "messages", "output", "attachments", "store"])
def test_baseline_freeze_refuses_nonredacted_sample_fields_despite_capture_false(tmp_path, field):
    baseline = baseline_with_real_inspect_log(tmp_path)
    file = baseline / "old.json"
    log = read_eval_log(file)
    sample = log.samples[0]
    if field == "input":
        sample.input = "synthetic confidential question"
    elif field == "target":
        sample.target = "synthetic confidential answer"
    elif field == "messages":
        sample.messages = [ChatMessageUser(content="synthetic confidential message")]
    elif field == "output":
        sample.output.completion = "synthetic confidential output"
    elif field == "attachments":
        sample.attachments = {"private-file": "synthetic confidential attachment"}
    else:
        sample.store = {"secret": "synthetic confidential store"}
    write_eval_log(log, location=file)

    with pytest.raises(ValueError, match="contains unredacted sample content"):
        _validate_baseline_target(baseline, run_dir(tmp_path), False)
    assert file.is_file()

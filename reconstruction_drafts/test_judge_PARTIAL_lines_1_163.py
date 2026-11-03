import asyncio
import hashlib
import json
import re
from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import EvalSample, read_eval_log
from inspect_ai.model import ChatMessageAssistant, ChatMessageSystem, ChatMessageTool, ChatMessageUser, ModelOutput
from inspect_ai.scorer import Score
from inspect_ai.solver import solver

import agent_accelerator.judge as judge_module
import agent_accelerator.run as run_module
from agent_accelerator.cli import EXIT_ERROR, build_parser, main
from agent_accelerator.compare import load_results
from agent_accelerator.dataset import dataset_sha256
from agent_accelerator.judge import (
    DEFAULT_RUBRIC,
    JUDGE,
    JUDGE_DOUBLE,
    SAFE_JUDGE_METADATA,
    TOOL_RESULTS_MAX_CHARS,
    Criterion,
    JudgeConfig,
    JudgedEpoch,
    JudgeOutputError,
    data_marker,
    golden_prompt,
    judge_error,
    judge_provenance,
    judged_epochs,
    load_golden,
    load_rubric,
    parse_judgement,
    reference_free_prompt,
    resolve_judge_model,
    tool_results_text,
)
from agent_accelerator.judge_double import judge_reply
from agent_accelerator.report import render_run
from agent_accelerator.run import _scrub_score, build_task, run_task
from agent_accelerator.scorers import CASE_CHECKS

DEFAULT_NAMES = ["answers_question", "no_unsupported_claims", "follows_format", "safe_and_on_topic"]
ENCE_LINE = re.compile(r"<<<(BEGIN|END)-([A-Z]+) ([^>]*)>>>")


def write(path: Path, text: str, newline: str = "\n") -> Path:
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return path


def golden_line(**fields) -> str:
    return json.dumps(fields)


# load_golden


def test_load_golden_returns_entries_by_id_and_skips_blank_lines(tmp_path):
    # Witness: "s28 golden blank lines" (drop the blank-line skip) makes line 2 a validation error.
    path = write(
        tmp_path / "g.jsonl",
        "\n".join([golden_line(id="a", reference="ra", label="pass"), "   ", golden_line(id="b", reference="rb"), ""]),
    )

    entries = load_golden(path, {"a", "b"})

    assert list(entries) == ["a", "b"]
    assert (entries["a"].reference, entries["a"].label) == ("ra", "pass")
    assert (entries["b"].reference, entries["b"].label) == ("rb", None)


@pytest.mark.parametrize(
    ("second_line", "message"),
    [
        (golden_line(id="b", reference="rb", score=1), "invalid golden entry"),
        (golden_line(id="b", reference="rb", label="maybe"), "invalid golden entry"),
        (golden_line(id="a", reference="again"), "duplicate golden id 'a'"),
    ],
    ids=["extra-field", "bad-label", "duplicate-id"],
)
def test_load_golden_rejects_a_bad_line_naming_its_line_number(tmp_path, second_line, message):
    # Witnesses: "s28 golden extra allowed" (extra="ignore") passes extra-field; "s28 golden label any string"
    # (label: str | None) passes bad-label; "s28 golden duplicates allowed" passes duplicate-id; "s28 golden line
    # numbers" (start=0) reports :1: for every id.
    path = write(tmp_path / "g.jsonl", golden_line(id="a", reference="ra") + "\n" + second_line + "\n")

    with pytest.raises(ValueError, match=rf"g\.jsonl:2: {re.escape(message)}"):
        load_golden(path, {"a", "b"})


def test_load_golden_rejects_a_file_with_no_entries(tmp_path):
    # Witness: "s28 golden empty allowed" returns {} for a file of blank lines.
    path = write(tmp_path / "g.jsonl", "\n  \n")

    with pytest.raises(ValueError, match="golden file is empty"):
        load_golden(path, {"a"})


def test_load_golden_names_ids_not_in_the_dataset_sorted(tmp_path):
    # Witnesses: "s28 golden unknown ids ignored" accepts the file; "s28 golden unknown ids unsorted" names them
    # in file order (zeta, alpha).
    path = write(
        tmp_path / "g.jsonl",
        "\n".join(golden_line(id=i, reference="r") for i in ["zeta", "known", "alpha"]),
    )

    with pytest.raises(ValueError, match="golden ids not in the dataset: alpha, zeta$"):
        load_golden(path, {"known"})


def test_load_golden_without_case_ids_skips_the_id_check_and_missing_cases_are_allowed(tmp_path):
    # Witness: "s28 golden case_ids None checked" (treat None as an empty set) rejects every id; "s28 golden
    # missing ids rejected" (symmetric difference) rejects the dataset case "other" that has no entry.
    path = write(tmp_path / "g.jsonl", golden_line(id="only", reference="r"))

    assert list(load_golden(path, None)) == ["only"]
    assert list(load_golden(path, {"only", "other"})) == ["only"]


# load_rubric


def test_load_rubric_none_gives_the_four_built_in_criteria_in_order():
    # Witness: "s28 default rubric reversed" returns the built-in criteria last first.
    rubric = load_rubric(None)

    assert [c.name for c in rubric] == DEFAULT_NAMES
    assert all(c.description for c in rubric)


def test_load_rubric_reads_a_valid_file(tmp_path):
    # Control for the rejections below: digits and underscores after the first letter are valid names.
    # Witness: "s28 rubric name pattern" (^ [a-z_]+$) rejects "tone_2".
    path = write(tmp_path / "r.json", json.dumps([{"name": "tone_2", "description": "Polite."}]))

    assert load_rubric(path) == [Criterion(name="tone_2", description="Polite.")]


@pytest.mark.parametrize(
    ("criteria", "message"),
    [
        ([{"name": "Tone", "description": "d"}], "invalid rubric"),
        ([{"name": "2tone", "description": "d"}], "invalid rubric"),
        ([{"name": "tone", "description": ""}], "invalid rubric"),
        ([], "rubric has no criteria"),
        ([{"name": "tone", "description": "d"}, {"name": "tone", "description": "e"}], "duplicate criterion names"),
        ([{"name": "tone", "description": "d", "weight": 2}], "invalid rubric"),
    ],
    ids=["uppercase-name", "leading-digit", "empty-description", "empty-list", "duplicate-names", "extra-field"],
)
def test_load_rubric_rejects_an_invalid_file(tmp_path, criteria, message):
    # Witnesses: "s28 rubric name uppercase" passes uppercase-name; "s28 rubric name leading digit" passes
    # leading-digit; "s28 rubric empty description" (min_length=0) passes empty-description; "s28 rubric empty allowed"
    # passes empty-list; "s28 rubric duplicates allowed" passes duplicate-names; "s28 rubric extra allowed" passes extra-field.
    path = write(tmp_path / "r.json", json.dumps(criteria))

    with pytest.raises(ValueError, match=message):
        load_rubric(path)


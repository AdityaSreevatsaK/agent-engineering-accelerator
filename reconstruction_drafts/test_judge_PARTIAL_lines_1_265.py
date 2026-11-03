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



# judge_provenance


def test_provenance_hashes_golden_and_rubric_files_like_the_dataset_ignoring_crlf(tmp_path):
    # Witnesses: "s28 provenance golden raw bytes" and "s28 provenance rubric raw bytes" (hashlib over read_bytes)
    # make the CRLF copy hash differently.
    golden_text = golden_line(id="a", reference="r") + "\n"
    rubric_text = json.dumps([{"name": "tone", "description": "d"}]) + "\n"
    lf = judge_provenance(
        JudgeConfig("m", write(tmp_path / "g_lf.jsonl", golden_text), write(tmp_path / "r_lf.json", rubric_text))
    )
    crlf = judge_provenance(
        JudgeConfig(
            "m",
            write(tmp_path / "g_crlf.jsonl", golden_text, "\r\n"),
            write(tmp_path / "r_crlf.json", rubric_text, "\r\n"),
        )
    )

    assert lf["golden_sha256"] == hashlib.sha256(golden_text.encode()).hexdigest()
    assert lf["rubric_sha256"] == hashlib.sha256(rubric_text.encode()).hexdigest()
    assert lf["golden_sha256"] == dataset_sha256(tmp_path / "g_crlf.jsonl")
    assert (crlf["golden_sha256"], crlf["rubric_sha256"]) == (lf["golden_sha256"], lf["rubric_sha256"])
    assert lf["golden_path"] == (tmp_path / "g_lf.jsonl").as_posix()
    assert lf["rubric_path"] == (tmp_path / "r_lf.json").as_posix()


def test_provenance_without_files_has_no_golden_and_a_stable_default_rubric_hash():
    # Witnesses: "s28 provenance default rubric unhashed" (None for the default) fails the hash; "s36 prompt
    # version not bumped" (1) fails prompt_version. The default hash is derived here from the criteria load_rubric
    # returns. Pairwise provenance is checked against this one in test_judge_pairwise.
    provenance = judge_provenance(JudgeConfig("bedrock/x"))
    expected = hashlib.sha256(json.dumps([c.model_dump() for c in load_rubric(None)]).encode()).hexdigest()

    assert provenance == {
        "model": "bedrock/x",
        "prompt_version": 2,
        "golden_path": None,
        "golden_sha256": None,
        "rubric_path": None,
        "rubric_sha256": expected,
    }
    assert judge_provenance(JudgeConfig("other"))["rubric_sha256"] == expected


# Prompts

QUESTION = "Is the claim within policy?"
REFERENCE = "approve"


def blocks(user: str) -> list[tuple[str, str, str]]:
    return FENCE_LINE.findall(user)


def prompts(answer: str) -> dict[str, tuple[str, str]]:
    return {
        "golden": golden_prompt(QUESTION, REFERENCE, answer),
        "reference_free": reference_free_prompt(QUESTION, answer, load_rubric(None)),
    }


@pytest.mark.parametrize("mode", ["golden", "reference_free"])
def test_prompt_marker_is_deterministic_and_changes_with_the_answer(mode):
    # Witnesses: "s28 golden marker omits answer" and "s28 reference-free marker omits answer" leave the marker
    # unchanged when only the answer changes.
    first, again, other = prompts("yes")[mode], prompts("yes")[mode], prompts("no")[mode]

    assert first == again
    assert {m for _, _, m in blocks(first[1])} != {m for _, _, m in blocks(other[1])}


@pytest.mark.parametrize(
    ("mode", "names"),
    [("golden", ["QUESTION", "REFERENCE", "ANSWER"]), ("reference_free", ["QUESTION", "ANSWER"])],
)
def test_every_block_is_fenced_with_the_marker_named_in_the_system_message(mode, names):
    # Witnesses: "s28 golden reference fence other marker" fences REFERENCE with a different code; "s28 system
    # marker not formatted" leaves {marker} unformatted in the system message.
    system, user = prompts("an answer")[mode]

    found = blocks(user)
    [marker] = {m for _, _, m in found}
    assert found == [(edge, name, marker) for name in names for edge in ("BEGIN", "END")]
    assert re.fullmatch(r"[0-9a-f]{16}", marker)
    assert f"<<<BEGIN NAME {marker}>>>" in system


def test_reference_free_criteria_are_listed_in_the_system_message_only():
    # Witness: "s28 criteria in user message" moves the criteria list into the user message.
    rubric = [Criterion(name="tone", description="Polite."), Criterion(name="brevity", description="Short.")]

    system, user = reference_free_prompt(QUESTION, "an answer", rubric)

    assert re.findall(r"^- ([a-z_]+): (.*)$", system, flags=re.MULTILINE) == [
        ("tone", "Polite."),
        ("brevity", "Short."),
    ]
    assert "Polite." not in user and "brevity" not in user


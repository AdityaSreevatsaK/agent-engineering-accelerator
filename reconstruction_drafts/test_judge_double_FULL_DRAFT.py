import json

import pytest

from agent_accelerator.judge import Criterion, golden_prompt, load_rubric, parse_judgement, reference_free_prompt
from agent_accelerator.judge_double import NOT_UNDERSTOOD, judge_reply

QUESTION = "What is the decision?"


def golden_verdict(answer: str, reference: str) -> str:
    return json.loads(judge_reply(*golden_prompt(QUESTION, reference, answer)))["verdict"]


@pytest.mark.parametrize(
    ("answer", "reference", "verdict"),
    [
        ('{"b": [1, 2], "a": {"y": 1, "x": 2}}', '{"a": {"x": 2, "y": 1}, "b": [1, 2]}', "pass"),
        ('{"a": 1, "b": [2, 1]}', '{"b": [1, 2], "a": 1}', "fail"),
        ('{"a": 1}', '{"a": 2}', "fail"),
    ],
    ids=["key-order-ignored", "list-order-kept", "value-differs"],
)
def test_golden_json_answers_are_compared_as_json(answer, reference, verdict):
    # Witness: "s28 double json compared as text" fails key-order-ignored.
    assert golden_verdict(answer, reference) == verdict


@pytest.mark.parametrize(
    ("answer", "reference", "verdict"),
    [
        ("  The claim is  APPROVED.\\n", "the claim is approved", "pass"),
        ("the claim is approved", "The claim is approved.", "pass"),
        ("the claim is rejected", "the claim is approved", "fail"),
        ("the claim is approved!", "the claim is approved", "fail"),
    ],
    ids=["case-whitespace-full-stop", "full-stop-on-reference", "words-differ", "other-punctuation-kept"],
)
def test_golden_text_answers_ignore_case_whitespace_and_a_trailing_full_stop(answer, reference, verdict):
    # Witness: "s28 double no normalise" (answer == reference) fails both pass ids.
    assert golden_verdict(answer, reference) == verdict


def test_reference_free_fails_every_criterion_of_a_blank_answer_and_passes_a_present_one():
    # Witnesses: "s28 double blank passes" (answered = True) passes the blank answer; "s28 double criteria ignored"
    # replies with no criteria, which parse_judgement rejects. The reply is read back through the real parser.
    rubric = [Criterion(name="tone", description="Polite."), *load_rubric(None)]

    blank = parse_judgement(judge_reply(*reference_free_prompt(QUESTION, " \\n ", rubric)), "reference_free", rubric)
    present = parse_judgement(judge_reply(*reference_free_prompt(QUESTION, "no", rubric)), "reference_free", rubric)

    assert list(blank.criteria) == [c.name for c in rubric]
    assert (blank.passed, {r.verdict for r in blank.criteria.values()}) == (False, {"fail"})
    assert (present.passed, {r.verdict for r in present.criteria.values()}) == (True, {"pass"})


def test_a_prompt_without_the_marker_in_the_system_message_is_not_understood():
    # Witness: "s28 double marker from user" (search the user message too) finds the user's code and replies JSON.
    _, user = golden_prompt(QUESTION, "approve", "approve")

    assert judge_reply("Grade the answer.", user) == NOT_UNDERSTOOD


def test_a_prompt_without_an_answer_block_is_not_understood():
    # Witness: "s28 double missing answer guessed" (a missing ANSWER block read as "") replies JSON.
    system, user = golden_prompt(QUESTION, "approve", "approve")
    without_answer = user[: user.index("\\n\\n<<<BEGIN ANSWER")]

    assert judge_reply(system, user) != NOT_UNDERSTOOD
    assert judge_reply(system, without_answer) == NOT_UNDERSTOOD
import pytest

from agent_accelerator.judge import pairwise_prompt, parse_pair_judgement
from agent_accelerator.judge_double import NOT_UNDERSTOOD, judge_reply

QUESTION = "What is the decision?"


def verdict_for_a(answer_a: str, answer_b: str) -> str:
    """The double's verdict for answer A, read back through the real pairwise parser."""
    return parse_pair_judgement(judge_reply(*pairwise_prompt(QUESTION, answer_a, answer_b, [])), True).verdict


@pytest.mark.parametrize(
    ("answer_a", "answer_b"),
    [
        ('{"b": [1, 2], "a": {"y": 1, "x": 2}}', '{"a": {"x": 2, "y": 1}, "b": [1, 2]}'),
        ("  The claim is  APPROVED.\n", "the claim is approved"),
        ("the claim is approved", "The claim is approved."),
        ("", "  "),
    ],
    ids=["json-key-order", "case-whitespace-full-stop", "full-stop-on-b", "both-blank"],
)
def test_equivalent_answers_are_the_same_in_both_orders(answer_a, answer_b):
    # Witness: "s33 double pair exact" (answer_a == answer_b) makes every id differ, so A wins in both orders.
    assert [verdict_for_a(answer_a, answer_b), verdict_for_a(answer_b, answer_a)] == ["same", "same"]


@pytest.mark.parametrize(
    ("answer_a", "answer_b", "expected"),
    [("approved", " \n ", "better"), (" \n ", "approved", "worse")],
    ids=["b-blank", "a-blank"],
)
def test_exactly_one_blank_answer_loses_in_either_position(answer_a, answer_b, expected):
    # Witnesses: "s33 double pair blank first" (always "A" for a blank) fails a-blank; "s33 double pair blank
    # ignored" (no blank rule) fails a-blank.
    assert verdict_for_a(answer_a, answer_b) == expected


@pytest.mark.parametrize(
    ("answer_a", "answer_b"),
    [("approved", "rejected"), ('{"a": 1, "b": [2, 1]}', '{"b": [1, 2], "a": 1}'), ("approved!", "approved")],
    ids=["words-differ", "json-list-order", "other-punctuation"],
)
def test_differing_answers_go_to_the_one_shown_first_in_both_orders(answer_a, answer_b):
    # The double's deliberate position bias, which the scorer's swap exists to catch.
    # Witness: "s33 double pair second" (prefer B) fails every id.
    assert [verdict_for_a(answer_a, answer_b), verdict_for_a(answer_b, answer_a)] == ["better", "better"]


@pytest.mark.parametrize("missing", ["ANSWER_A", "ANSWER_B"])
def test_a_pairwise_prompt_missing_an_answer_block_is_not_understood(missing):
    # Witness: "s33 double pair one block enough" (`or`) treats the missing block as present and replies JSON.
    system, user = pairwise_prompt(QUESTION, "approved", "rejected", [])
    start = user.index(f"<<<BEGIN {missing} ")
    end = user.index(">>>", user.index(f"<<<END {missing} ")) + 3
    without = user[:start] + user[end:]

    assert judge_reply(system, user) != NOT_UNDERSTOOD
    assert judge_reply(system, without) == NOT_UNDERSTOOD

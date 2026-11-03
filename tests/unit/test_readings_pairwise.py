import pytest

from agent_accelerator import readings
from agent_accelerator.judge import BASELINE_AGENT_ERROR, NOT_IN_BASELINE, JudgedEpoch


def epoch(case_id, outcome, mode="pairwise", **fields) -> JudgedEpoch:
    return JudgedEpoch(case_id, outcome, mode, "judge/m", **fields)


def judged(case_id, pairwise, outcome=None, disagreed=False) -> JudgedEpoch:
    outcome = outcome or ("fail" if pairwise == "worse" else "pass")
    return epoch(case_id, outcome, pairwise=pairwise, order_disagreed=disagreed)


def gap(case_id, reason=NOT_IN_BASELINE) -> JudgedEpoch:
    return epoch(case_id, "not_judged", not_judged=reason)


def judge_readings(*epochs: JudgedEpoch) -> list[str]:
    return readings.judge_readings(epochs, [], 0, None)


def find(found: list[str], fragment: str) -> list[str]:
    return [r for r in found if fragment in r]


# Baseline gaps


@pytest.mark.parametrize(
    ("gaps", "start", "names", "end"),
    [
        ([gap("d")], "1 try was not judged", " d ", "leaves it out."),
        ([gap("e", BASELINE_AGENT_ERROR), gap("d")], "2 tries were not judged", " d and e ", "leaves them out."),
    ],
    ids=["one", "two-sorted"],
)
def test_baseline_gaps_are_read_as_their_own_reason_naming_the_cases(gaps, start, names, end):
    # Witnesses: "s33 readings gaps as agent errors" (count gaps with agent errors) adds an agent-error reading;
    # "s33 readings gap names unsorted" names e before d.
    found = judge_readings(judged("a", "same"), *gaps)

    [reading] = find(found, "baseline has no answer")
    assert (reading.startswith(start), names in reading, reading.endswith(end)) == (True, True, True)
    assert find(found, "because the agent errored") == []


def test_an_agent_error_in_a_pairwise_run_is_still_read_as_an_agent_error_apart_from_the_gap():
    # Witness: "s33 readings agent errors only unrecorded" (count only not_judged None) drops g's recorded
    # "agent_error", which the golden tests in test_readings.py cannot see because their epochs record no reason.
    found = judge_readings(judged("a", "same"), gap("d"), epoch("g", "not_judged", not_judged="agent_error"))

    [reading] = find(found, "because the agent errored")
    assert reading.startswith("1 try was not judged")
    assert len(find(found, "baseline has no answer")) == 1


# Worse, or none worse


def test_worse_answers_are_named_once_each_sorted_and_the_none_worse_reading_is_absent():
    # c is worse in two epochs and b in one, so names are de-duplicated and sorted.
    # Witness: "s33 readings worse unsorted" names them in epoch order.
    found = judge_readings(judged("c", "worse"), judged("a", "better"), judged("b", "worse"), judged("c", "worse"))

    [reading] = find(found, "worse than the baseline's, so")
    assert reading.startswith("The answers to b and c were worse")
    assert find(found, "No answer was judged worse") == []


@pytest.mark.parametrize(
    ("epochs", "expected"),
    [
        ([judged("a", "same"), judged("b", "same")], "No answer was judged worse than the baseline's."),
        (
            [judged("a", "better"), judged("b", "same")],
            "No answer was judged worse than the baseline's; 1 try was better.",
        ),
        (
            [judged("a", "better"), judged("b", "better"), judged("c", "same")],
            "No answer was judged worse than the baseline's; 2 tries were better.",
        ),
    ],
    ids=["none-better", "one-better", "two-better"],
)
def test_with_no_worse_answer_the_reading_counts_better_tries_only_when_there_are_some(epochs, expected):
    # Witnesses: "s33 readings better tail always" adds "; 0 tries were better"; "s33 readings better counts all"
    # (count every judged try) gives 2 and 3.
    assert find(judge_readings(*epochs), "No answer was judged worse") == [expected]


def test_with_only_baseline_gaps_there_is_no_worse_or_none_worse_reading():
    # Witness: "s33 readings none worse without verdicts" (elif -> else) says no answer was worse with none judged.
    found = judge_readings(gap("a"), gap("b", BASELINE_AGENT_ERROR))

    assert find(found, "judged worse") + find(found, "worse than the baseline's, so") == []
    assert len(find(found, "baseline has no answer")) == 1


# Order disagreements


def test_disagreements_in_a_single_epoch_run_are_counted_in_cases_out_of_the_judged_cases():
    # Three cases judged, one disagreed; the gap d is neither judged nor counted.
    # Witnesses: "s33 readings disagreement over all epochs" says "of 4 cases"; "s33 readings disagreement unit
    # fixed" says "tries".
    found = judge_readings(judged("a", "same", disagreed=True), judged("b", "better"), judged("c", "same"), gap("d"))

    [reading] = find(found, "swapped")
    assert " on 1 of 3 cases (a)" in reading


def test_disagreements_in_a_multi_epoch_run_are_counted_in_tries_naming_each_case_once():
    # Two cases at two epochs: a disagreed twice, b once, so 3 of 4 tries in cases a and b.
    # Witness: "s33 readings disagreement count fixed" (count cases, not tries) says "2 of 4".
    found = judge_readings(
        judged("a", "same", disagreed=True),
        judged("a", "same", disagreed=True),
        judged("b", "same", disagreed=True),
        judged("b", "better"),
    )

    [reading] = find(found, "swapped")
    assert " on 3 of 4 tries (a and b)" in reading


def test_disagreeing_cases_are_named_in_sorted_order_whatever_order_the_epochs_arrive_in():
    # c disagrees before b, so epoch order would name c first.
    # Witness: "s35 readings disagreement names unsorted" (names in epoch order) gives "(c and b)".
    found = judge_readings(
        judged("c", "same", disagreed=True), judged("a", "better"), judged("b", "same", disagreed=True)
    )

    [reading] = find(found, "swapped")
    assert " on 2 of 3 cases (b and c)" in reading


def test_without_disagreements_there_is_no_disagreement_reading():
    # Witness: "s33 readings disagreement unguarded" (if judged:) raises IndexError naming no disagreed cases.
    found = judge_readings(judged("a", "same"), judged("b", "better"))

    assert find(found, "swapped") == []
    assert find(found, "No answer was judged worse") != []


# Glossary


def test_pairwise_glossary_key_appears_only_when_some_epoch_was_judged_pairwise():
    # Witnesses: "s33 glossary pairwise always" adds it to the golden run; "s33 glossary pairwise dropped" loses it.
    golden = (epoch("a", "pass", mode="golden"),)
    mixed = (epoch("a", "pass", mode="golden"), judged("b", "same"))

    assert readings.judge_glossary_keys(golden, False) == ["judge error"]
    assert readings.judge_glossary_keys(mixed, True) == ["judge error", "pairwise", "kappa"]

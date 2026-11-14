import asyncio
import copy
from pathlib import Path

import pytest
from inspect_ai.log import EvalError, EvalSampleReductions, EvalSampleScore, read_eval_log, write_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT, NOANSWER, PARTIAL, Score, ScoreEdit
from inspect_ai.solver import TaskState

from agent_accelerator.compare import load_results
from agent_accelerator.run import scrub
from agent_accelerator.scorers import case_checks

CAPTURE = Path(__file__).parents[1] / "fixtures" / "calculator_capture_content.json"
REDACTED_STRINGS = (
    "What is 9 minus 4",
    "Tell me a joke",
    "You are a calculator",
)
ALLOWED_METADATA_KEYS = {"agent_error", "usage", "model_id"}


def read_capture():
    return read_eval_log(CAPTURE)


def test_scrub_removes_payload_fields_from_every_sample():
    log = read_capture()
    assert any({"case", "tool_calls"} & set(sample.metadata or {}) for sample in log.samples)

    scrubbed = scrub(log)

    for sample in scrubbed.samples:
        assert sample.input == "[REDACTED]"
        assert sample.target == "[REDACTED]"
        assert sample.messages == []
        assert sample.events == []
        assert sample.attachments == {}
        assert sample.store == {}
        assert sample.output.completion == ""
        assert sample.output.choices == []
        assert set(sample.metadata or {}) <= ALLOWED_METADATA_KEYS
        assert not {"case", "tool_calls"} & set(sample.metadata or {})


def test_scrub_empties_seeded_sample_attachments_and_store():
    log = read_capture()
    sample = log.samples[0]
    sample.attachments = {"payload.txt": "attachment payload"}
    sample.store = {"payload": "stored payload"}

    scrubbed = scrub(log)

    assert scrubbed.samples[0].attachments == {}
    assert scrubbed.samples[0].store == {}


def test_scrub_preserves_safe_metadata_keys_and_values():
    log = read_capture()
    sample = log.samples[0]
    safe_metadata = {
        "agent_error": "sample agent error",
        "usage": {"input_tokens": 17, "output_tokens": 8},
        "model_id": "test-model",
    }
    sample.metadata.update(safe_metadata)

    scrubbed = scrub(log)

    assert {key: scrubbed.samples[0].metadata[key] for key in safe_metadata} == safe_metadata


def test_scrub_redacts_agent_error_and_preserves_usage_and_model_id():
    log = read_capture()
    safe_metadata = {
        "agent_error": "RuntimeError: secret text",
        "usage": {"input_tokens": 17, "output_tokens": 8},
        "model_id": "test-model",
    }
    log.samples[0].metadata.update(safe_metadata)

    scrubbed_metadata = scrub(log).samples[0].metadata

    assert scrubbed_metadata["agent_error"] == "RuntimeError"
    assert scrubbed_metadata["usage"] == safe_metadata["usage"]
    assert scrubbed_metadata["model_id"] == safe_metadata["model_id"]


def test_scrub_redacts_eval_errors_and_load_results_keeps_case_error(tmp_path):
    log = read_capture()
    case_id = str(log.samples[0].id)
    seeded_error = EvalError(
        message="secret text",
        traceback="secret traceback",
        traceback_ansi="secret ANSI traceback",
    )
    log.samples[0].error = seeded_error
    log.error = seeded_error

    scrubbed = scrub(log)

    for error in (scrubbed.samples[0].error, scrubbed.error):
        assert error.message == "[REDACTED]"
        assert error.traceback == "[REDACTED]"
        assert error.traceback_ansi == "[REDACTED]"

    scrubbed_path = tmp_path / "scrubbed-errors.json"
    write_eval_log(scrubbed, location=scrubbed_path)

    assert load_results(scrubbed_path).cases[case_id].error is not None


def test_scrub_clears_sample_score_answers_without_changing_other_score_data():
    log = read_capture()
    before = {
        sample.id: {
            scorer: {
                "value": score.value,
                "explanation": score.explanation,
                "metadata": copy.deepcopy(score.metadata),
            }
            for scorer, score in sample.scores.items()
        }
        for sample in log.samples
    }
    next(iter(log.samples[0].scores.values())).answer = "sample sensitive answer"

    scrubbed = scrub(log)

    for sample in scrubbed.samples:
        for scorer, score in sample.scores.items():
            assert score.answer is None
            assert score.value == before[sample.id][scorer]["value"]
            assert score.explanation == before[sample.id][scorer]["explanation"]
            assert score.metadata == before[sample.id][scorer]["metadata"]


def test_scrub_clears_reduction_score_answers_without_changing_other_data():
    log = read_capture()
    reduction_scores = [score for reduction in log.reductions for score in reduction.samples]
    before = [
        {
            "value": score.value,
            "explanation": score.explanation,
            "metadata": copy.deepcopy(score.metadata),
        }
        for score in reduction_scores
    ]
    reduction_scores[0].answer = "reduction sensitive answer"

    scrubbed = scrub(log)

    after = [score for reduction in scrubbed.reductions for score in reduction.samples]
    assert len(after) == len(before)
    for score, original in zip(after, before, strict=True):
        assert score.answer is None
        assert score.value == original["value"]
        assert score.explanation == original["explanation"]
        assert score.metadata == original["metadata"]


def test_scrub_preserves_sample_ids_and_total_times():
    log = read_capture()
    before = [(sample.id, sample.total_time) for sample in log.samples]

    scrubbed = scrub(log)

    assert [(sample.id, sample.total_time) for sample in scrubbed.samples] == before


def test_scrub_serialisation_contains_none_of_the_fixture_payload_strings():
    log = read_capture()
    assert "What is 9 minus 4" in log.model_dump_json()

    serialised = scrub(log).model_dump_json()

    for secret in REDACTED_STRINGS:
        assert secret not in serialised


def test_load_results_preserves_case_pass_fail_after_scrubbing(tmp_path):
    original = load_results(CAPTURE)
    scrubbed_path = tmp_path / "scrubbed.json"
    scrubbed_path.write_text(scrub(read_capture()).model_dump_json(), encoding="utf-8")

    scrubbed_results = load_results(scrubbed_path)

    assert {case_id: case.passed for case_id, case in scrubbed_results.cases.items()} == {
        case_id: case.passed for case_id, case in original.cases.items()
    }


CUSTOM = "custom_judge"
SECRET = "custom scorer quoted the output"


def custom_score():
    return Score(value=1, answer=SECRET, explanation=SECRET, metadata={"quote": SECRET})


def test_scrub_clears_answer_explanation_and_metadata_of_custom_sample_scores():
    log = read_capture()
    for sample in log.samples:
        sample.scores[CUSTOM] = custom_score()

    scrubbed = scrub(log)

    for sample in scrubbed.samples:
        score = sample.scores[CUSTOM]
        assert (score.answer, score.explanation, score.metadata) == (None, None, None)
        assert score.value == 1


def test_scrub_clears_answer_explanation_and_metadata_of_custom_reduction_scores():
    log = read_capture()
    sample_id = log.samples[0].id
    log.reductions.append(
        EvalSampleReductions(
            scorer=CUSTOM,
            samples=[
                EvalSampleScore(
                    value=1, answer=SECRET, explanation=SECRET, metadata={"quote": SECRET}, sample_id=sample_id
                )
            ],
        )
    )

    scrubbed = scrub(log)

    [reduction] = [r for r in scrubbed.reductions if r.scorer == CUSTOM]
    [score] = reduction.samples
    assert (score.answer, score.explanation, score.metadata) == (None, None, None)
    assert score.value == 1


def test_scrub_keeps_case_checks_tool_call_count_so_the_report_can_show_it(tmp_path):
    # Witness: s16 scrub drops case_checks metadata (`score.metadata = None` for every scorer) gives None.
    log = read_capture()
    for sample in log.samples:
        sample.scores["case_checks"].metadata = {"checks": {}, "tool_call_count": 2}
    path = tmp_path / "scrubbed.json"
    write_eval_log(scrub(log), location=path)

    cases = load_results(path).cases

    assert len(cases) == 10
    assert {case.tool_calls for case in cases.values()} == {2.0}


def test_scrub_keeps_case_checks_explanation_but_clears_its_answer():
    log = read_capture()
    score = log.samples[0].scores["case_checks"]
    score.answer = SECRET
    score.explanation = "expected <redacted>, got <redacted>"

    scrubbed = scrub(log).samples[0].scores["case_checks"]

    assert scrubbed.answer is None
    assert scrubbed.explanation == "expected <redacted>, got <redacted>"


def edit():
    return ScoreEdit(value=0, answer=SECRET, explanation=SECRET, metadata={"quote": SECRET})


def test_scrub_clears_history_and_reason_of_custom_sample_scores():
    log = read_capture()
    for sample in log.samples:
        score = custom_score()
        score.reason = SECRET
        score.history = [edit()]
        sample.scores[CUSTOM] = score

    scrubbed = scrub(log)

    for sample in scrubbed.samples:
        score = sample.scores[CUSTOM]
        assert (score.history, score.reason) == ([], None)


def test_scrub_clears_case_checks_history_but_keeps_its_reason():
    log = read_capture()
    score = log.samples[0].scores["case_checks"]
    score.reason = "checks failed"
    score.history = [edit()]

    scrubbed = scrub(log).samples[0].scores["case_checks"]

    assert scrubbed.history == []
    assert scrubbed.reason == "checks failed"


def test_scrub_clears_history_and_reason_of_reduction_scores():
    log = read_capture()
    sample_id = log.samples[0].id
    log.reductions.append(
        EvalSampleReductions(
            scorer=CUSTOM,
            samples=[EvalSampleScore(value=1, reason=SECRET, history=[edit()], sample_id=sample_id)],
        )
    )
    case_checks_score = next(r for r in log.reductions if r.scorer == "case_checks").samples[0]
    case_checks_score.reason = "checks failed"
    case_checks_score.history = [edit()]

    scrubbed = scrub(log)

    [custom] = next(r for r in scrubbed.reductions if r.scorer == CUSTOM).samples
    assert (custom.history, custom.reason) == ([], None)
    case_checks = next(r for r in scrubbed.reductions if r.scorer == "case_checks").samples[0]
    assert (case_checks.history, case_checks.reason) == ([], "checks failed")


def test_scrub_serialisation_drops_secrets_held_only_in_history_and_reason():
    log = read_capture()
    for sample in log.samples:
        for score in sample.scores.values():
            score.history = [edit()]
        sample.scores[CUSTOM] = Score(value=1, reason=SECRET)

    serialised = scrub(log).model_dump_json()

    assert SECRET not in serialised


ARGUMENT_SECRET = "tool argument payload 0xB0B"


def test_case_checks_tool_use_survives_scrub_and_loads_without_any_argument_value(tmp_path):
    # Every sample is rescored with two identical calls carrying a secret argument, the second erroring.
    # Witnesses: s21 scorer drops tool metadata and s21 compare drops tool use give tool_use None; s21 scorer
    # ignores errors gives 0 results; s21 metadata keeps calls leaves the secret in the scrubbed log.
    log = read_capture()
    calls = [{"name": "calculator", "arguments": {"note": ARGUMENT_SECRET}}] * 2
    for sample in log.samples:
        state = TaskState(
            model="test-model",
            sample_id=sample.id,
            epoch=sample.epoch,
            input="x",
            messages=[],
            output=ModelOutput(completion=sample.output.completion),
            metadata={**sample.metadata, "tool_calls": calls, "tool_errors": [False, True]},
        )
        sample.scores["case_checks"] = asyncio.run(case_checks()(state, state.target))
    path = tmp_path / "scrubbed.json"
    write_eval_log(scrub(log), location=path)

    cases = load_results(path).cases

    assert ARGUMENT_SECRET not in path.read_text(encoding="utf-8")
    assert len(cases) == 10
    counts = {(c.tool_use.calls_per_epoch, tuple(c.tool_use.by_tool.items())) for c in cases.values()}
    assert counts == {((2,), (("calculator", 2),))}
    assert {(c.tool_use.results, c.tool_use.errors, c.tool_use.redundant) for c in cases.values()} == {(2, 1, 1)}
    # no_tool_for_chat expects no tool, so the call is wrong and recall is undefined; the rest expect calculator.
    selection = {case_id: (c.tool_use.precision, c.tool_use.recall) for case_id, c in cases.items()}
    assert selection.pop("no_tool_for_chat") == (0.0, None)
    assert set(selection.values()) == {(1.0, 1.0)}


def test_scrub_keeps_the_case_checks_output_digest_but_no_output_text(tmp_path):
    # The digest is what Consistency reads from a run kept without --capture-content.
    # Witness: s22 scrub clears case_checks metadata, s22 epoch digest dropped.
    output = "OUTPUT-TEXT-ONLY-IN-THE-COMPLETION"
    log = read_capture()
    for number, sample in enumerate(log.samples):
        sample.output.completion = output
        sample.scores["case_checks"].metadata = {"checks": {}, "output_digest": f"{number:016x}"}
    path = tmp_path / "scrubbed.json"
    scrubbed = scrub(log)
    write_eval_log(scrubbed, location=path)

    digests = {e.output_digest for case in load_results(path).cases.values() for e in case.epochs}

    assert digests == {f"{number:016x}" for number in range(10)}
    assert output not in scrubbed.model_dump_json()


def test_scrub_redacts_arbitrary_custom_scorer_values_in_samples_and_reductions():
    """Untrusted custom scorers can return sensitive output as their Score.value."""
    log = read_capture()
    sample_id = log.samples[0].id
    raw_value = SECRET
    log.samples[0].scores[CUSTOM] = Score(value=raw_value)
    log.reductions.append(
        EvalSampleReductions(
            scorer=CUSTOM,
            samples=[EvalSampleScore(value=raw_value, sample_id=sample_id)],
        )
    )

    scrubbed = scrub(log)

    assert scrubbed.samples[0].scores[CUSTOM].value == INCORRECT
    assert next(r for r in scrubbed.reductions if r.scorer == CUSTOM).samples[0].value == INCORRECT
    assert SECRET not in scrubbed.model_dump_json()


@pytest.mark.parametrize("value", [CORRECT, INCORRECT, PARTIAL, NOANSWER, 0, 1, 0.5])
def test_scrub_preserves_standard_grades_and_numeric_custom_scores(value):
    log = read_capture()
    log.samples[0].scores[CUSTOM] = Score(value=value)

    assert scrub(log).samples[0].scores[CUSTOM].value == value

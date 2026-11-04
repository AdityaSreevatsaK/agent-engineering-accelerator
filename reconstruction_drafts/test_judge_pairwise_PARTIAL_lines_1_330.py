import hashlib
import json
import re
from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import EvalError, EvalSample, read_eval_log, write_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score
from inspect_ai.solver import solver

import agent_accelerator.judge as judge_module
import agent_accelerator.run as run_module
from agent_accelerator.dataset import dataset_sha256
from agent_accelerator.judge import (
    BASELINE_AGENT_ERROR,
    JUDGE,
    JUDGE_DOUBLE,
    NOT_IN_BASELINE,
    SAFE_JUDGE_METADATA,
    Criterion,
    JudgeConfig,
    JudgeOutputError,
    baseline_dataset_warning,
    combine_orders,
    data_marker,
    judge,
    judge_provenance,
    judged_epochs,
    load_baseline,
    pairwise_prompt,
    parse_pair_judgement,
)
from agent_accelerator.run import build_task, run_task

QUESTION = "Is the claim within policy?"
FENCE_LINE = re.compile(r"<<<(BEGIN|END) ([A-Z_]+) ([^>]*)>>>")
VERDICTS = ("better", "same", "worse")


def write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


def marker_of(system: str) -> str:
    return re.search(r"<<<BEGIN NAME ([0-9a-f]{16})>>>", system).group(1)


def block(user: str, name: str, marker: str) -> str | None:
    found = re.search(rf"<<<BEGIN {name} {marker}>>>\n(.*?)\n<<<END {name} {marker}>>>", user, flags=re.DOTALL)
    return found.group(1) if found else None


def pair_reply(verdict: str, reason: str = "r", **extra) -> str:
    return json.dumps({"verdict": verdict, "reason": reason, **extra})


# The agent and the judge model. fixed_answers and the evaluate fixture follow test_judge.py's, extended with a
# baseline run; they are repeated rather than imported because test files here do not import from each other.
# TODO(PFITAPP-7282): move to tests/conftest.py


def fixed_answers(answers: dict[str, str | list[str]], agent_errors: tuple[str, ...]):
    """Stands in for the agent; a list answers epoch n with its nth item. Closed over, so not in the log."""

    @solver(name="fixed_answers")
    def fixed():
        async def solve(state, generate):
            case_id = str(state.sample_id)
            answer = answers[case_id]
            answer = answer if isinstance(answer, str) else answer[state.epoch - 1]
            state.output = ModelOutput.from_content("fake-agent", answer)
            if case_id in agent_errors:
                state.metadata["agent_error"] = "RuntimeError: agent failed"
            return state

        return solve

    return fixed()


class PairJudge:
    """A judge model that records each prompt and the (ANSWER_A, ANSWER_B) pair it shows, and replies per call.

    `reply` is a reply text, or a callable taking (answer_a, answer_b). `error` is raised on call number `error_on`
    (1-based), or on every call when error_on is None.
    """

    def __init__(self, reply="", error: Exception | None = None, error_on: int | None = None):
        self.reply, self.error, self.error_on = reply, error, error_on
        self.calls: list[list[str]] = []
        self.pairs: list[tuple[str | None, str | None]] = []

    async def generate(self, messages):
        system, user = messages[0].text, messages[-1].text
        self.calls.append([m.text for m in messages])
        marker = marker_of(system)
        pair = (block(user, "ANSWER_A", marker), block(user, "ANSWER_B", marker))
        self.pairs.append(pair)
        if self.error and self.error_on in (None, len(self.calls)):
            raise self.error
        text = self.reply(*pair) if callable(self.reply) else self.reply
        return ModelOutput.from_content("pair-judge", text)


def prefer(answer: str):
    """A consistent judge: names whichever position holds this answer."""
    return lambda a, b: pair_reply("A" if a == answer else "B")


@pytest.fixture
def scripted(monkeypatch):
    def install(judge_model: PairJudge) -> PairJudge:
        monkeypatch.setattr(judge_module, "resolve_judge_model", lambda name: judge_model)
        return judge_model

    return install


@pytest.fixture
def evaluate(monkeypatch, tmp_path):
    """Runs cases {id: (question, answer)} through build_task and run_task and returns (log, run dir)."""

    def run(cases, baseline=None, capture=False, agent_errors=(), judge=JUDGE_DOUBLE, rubric=None, raw=False):
        answers = {case_id: answer for case_id, (_, answer) in cases.items()}
        monkeypatch.setattr(
            run_module, "_adapter_solver", lambda adapter, agent, **maps: fixed_answers(answers, tuple(agent_errors))
        )
        dataset = write(
            tmp_path / "dataset.jsonl", "\n".join(json.dumps({"id": i, "input": q}) for i, (q, _) in cases.items())
        )
        config = JudgeConfig(judge, None, rubric, baseline) if judge else None
        task = build_task(dataset, "unused:agent", capture_content=capture, judge_config=config)
        if raw:  # Inspect's own log, before run_task scrubs it
            [log] = inspect_eval(task, model="mockllm/model", log_dir=(tmp_path / "raw").as_posix(), display="none")
            return log, None
        run_dir = tmp_path / f"run{len(list(tmp_path.glob('run*')))}"
        run_dir.mkdir()
        return read_eval_log(run_task(task, run_dir, capture)), run_dir

    return run


@pytest.fixture
def baseline_run(evaluate):
    """A captured, unjudged run of {id: answer} (question QUESTION) that pairwise runs can use as their baseline."""

    def make(answers: dict[str, str], agent_errors=()) -> Path:
        _, run_dir = evaluate(
            {i: (QUESTION, a) for i, a in answers.items()}, capture=True, judge=None, agent_errors=agent_errors
        )
        return run_dir

    return make


@pytest.fixture
def pairwise(evaluate, baseline_run):
    """Judges {id: answer} against a baseline of {id: answer}; returns the judge score per case id."""

    def run(answers, baseline, baseline_errors=(), agent_errors=(), capture=False, raw=False, rubric=None):
        base = baseline_run(baseline, baseline_errors)
        log, _ = evaluate(
            {i: (QUESTION, a) for i, a in answers.items()},
            baseline=base,
            capture=capture,
            agent_errors=agent_errors,
            raw=raw,
            rubric=rubric,
        )
        return {str(s.id): s.scores[JUDGE] for s in log.samples}

    return run


# load_baseline, on logs written with chosen samples and metadata


@pytest.fixture
def write_log(baseline_run, tmp_path):
    """Writes a log like a captured run's, with the given eval metadata changes and samples, and returns its path.

    Samples are (id, epoch, answer, agent_error, sample_error), stored in the order given. Inspect's writer sorts
    samples by epoch then id, so the file is reordered after writing; reading keeps the stored order.
    """
    template = read_eval_log(next(baseline_run({"t": "template"}).glob("*.json")))

    def make(samples, name="baseline.json", **metadata):
        log = template.model_copy(deep=True)
        log.eval.metadata = {k: v for k, v in ({**log.eval.metadata, **metadata}).items() if v is not ...}
        log.samples = [
            EvalSample(
                id=case_id,
                epoch=epoch,
                input=QUESTION,
                target="",
                output=ModelOutput.from_content("fake-agent", answer),
                metadata={"agent_error": "RuntimeError: x"} if agent_error else {},
                error=EvalError(message="m", traceback="t", traceback_ansi="t") if sample_error else None,
            )
            for case_id, epoch, answer, agent_error, sample_error in samples
        ]
        path = tmp_path / name
        write_eval_log(log, path.as_posix())
        stored = json.loads(path.read_text(encoding="utf-8"))
        order = [(case_id, epoch) for case_id, epoch, *_ in samples]
        stored["samples"] = sorted(stored.get("samples") or [], key=lambda s: order.index((s["id"], s["epoch"])))
        path.write_text(json.dumps(stored), encoding="utf-8")
        assert [(s.id, s.epoch) for s in read_eval_log(path.as_posix()).samples or []] == order
        return path

    return make


OK = [("a", 1, "answer a", False, False)]


@pytest.mark.parametrize(
    "capture",
    [..., False, "true", 1],
    ids=["missing", "false", "string-true", "one"],
)
def test_load_baseline_rejects_a_log_not_captured_with_exactly_true_naming_the_flag(write_log, capture):
    # Witnesses: "s33 baseline capture truthy" (`not metadata.get(...)`) accepts string-true and one; "s33 baseline
    # capture only false" (`is False`) accepts missing, string-true and one.
    path = write_log(OK, capture_content=capture)

    with pytest.raises(ValueError, match="rerun the baseline with --capture-content"):
        load_baseline(path)


def test_load_baseline_accepts_a_captured_log_and_a_run_directory_alike(write_log, baseline_run):
    # Control for the rejections above, and the run-directory form of the argument.
    run_dir = baseline_run({"a": "answer a"})

    from_dir = load_baseline(run_dir)

    assert load_baseline(write_log(OK)).answers == {"a": "answer a"}
    assert from_dir.answers == {"a": "answer a"}
    assert from_dir.log_path == next(run_dir.glob("*.json"))


def test_load_baseline_takes_the_lowest_epoch_without_an_error_whatever_the_stored_order(write_log):
    # a: epoch 1 agent error, so epoch 2; b: epoch 1 sample error, so epoch 2. Stored last epoch first.
    # Witnesses: "s33 baseline unsorted" takes a3 (stored first); "s33 baseline agent error kept" takes a1; "s33
    # baseline sample error kept" takes b1; "s33 baseline last epoch wins" (drop `case_id not in answers`) takes a3.
    path = write_log(
        [
            ("a", 3, "a3", False, False),
            ("b", 2, "b2", False, False),
            ("a", 1, "a1", True, False),
            ("a", 2, "a2", False, False),
            ("b", 1, "b1", False, True),
        ]
    )

    assert load_baseline(path).answers == {"a": "a2", "b": "b2"}


def test_load_baseline_puts_an_all_errored_case_in_errored_and_keeps_an_empty_answer(write_log):
    # d answered "" in epoch 1, so "" is its answer even though epoch 2 has text.
    # Witnesses: "s33 baseline errored empty" (frozenset()) loses c; "s33 baseline empty answer skipped" (`not
    # answers.get(case_id)`) takes "later" for d.
    path = write_log(
        [
            ("c", 1, "c1", True, False),
            ("c", 2, "c2", False, True),
            ("d", 1, "", False, False),
            ("d", 2, "later", False, False),
        ]
    )

    baseline = load_baseline(path)

    assert (baseline.answers, baseline.errored) == ({"d": ""}, frozenset({"c"}))


@pytest.mark.parametrize(
    ("dataset", "expected"),
    [("ab" * 32, "ab" * 32), (..., None), (12345, None)],
    ids=["string", "missing", "not-a-string"],
)
def test_load_baseline_reads_the_dataset_hash_and_only_a_string_one(write_log, dataset, expected):
    # Witness: "s33 baseline dataset any type" (keep the value whatever its type) gives 12345.
    path = write_log(OK, dataset_sha256=dataset, run_id="base-run-7")

    baseline = load_baseline(path)

    assert baseline.dataset_sha256 == expected
    assert baseline.run_id == "base-run-7"


def test_load_baseline_from_a_real_run_records_its_run_id_and_dataset_hash(baseline_run, tmp_path):
    # Witness: "s33 baseline run id from inspect" (log.eval.run_id) gives Inspect's id, not the run directory's.
    run_dir = baseline_run({"a": "x"})

    baseline = load_baseline(run_dir)

    assert baseline.run_id == run_dir.name
    assert baseline.dataset_sha256 == dataset_sha256(tmp_path / "dataset.jsonl")


# baseline_dataset_warning


def baseline_with(dataset: str | None):
    return judge_module.Baseline("r", Path("b.json"), {}, frozenset(), dataset)


def test_dataset_warning_is_none_when_the_hashes_match():
    # Witness: "s33 dataset warning always" (drop the equality return) warns on a match.
    assert baseline_dataset_warning(baseline_with("a" * 64), "a" * 64) is None


def test_dataset_warning_names_both_hashes_to_twelve_characters_when_they_differ():
    # Witness: "s33 dataset warning prefix" ([:8]) cuts both hashes short.
    old, new = "0123456789abcdef" * 4, "fedcba9876543210" * 4

    text = baseline_dataset_warning(baseline_with(old), new)

    assert f"{old[:12]}" in text and f"{new[:12]}" in text
    assert old[:13] not in text and new[:13] not in text
    assert "may not be comparable" in text


def test_dataset_warning_says_it_cannot_check_a_baseline_without_a_hash():
    # Witness: "s33 dataset warning none unchecked" (drop the None branch) fails on None[:12].
    assert "cannot be checked" in baseline_dataset_warning(baseline_with(None), "a" * 64)

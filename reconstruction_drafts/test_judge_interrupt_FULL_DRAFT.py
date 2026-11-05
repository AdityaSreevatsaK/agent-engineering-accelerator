import asyncio
import json
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelName, ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target
from inspect_ai.solver import TaskState, solver

import agent_accelerator.judge as judge_module
import agent_accelerator.run as run_module
from agent_accelerator.compare import load_results
from agent_accelerator.judge import (
    BASELINE_AGENT_ERROR,
    BASELINE_INTERRUPTED,
    INTERRUPTED,
    JUDGE,
    JUDGE_DOUBLE,
    JudgeConfig,
    JudgedEpoch,
    judge,
    load_baseline,
)
from agent_accelerator.readings import judge_readings
from agent_accelerator.report import render_run
from agent_accelerator.run import build_task, run_task

# Outcomes of a case-epoch for the stand-in agent: an answer, or one of these.
STOPPED = "interrupted"
FAILED = "agent_error"
BOTH = "agent_error_and_interrupted"


def outcomes_solver(outcomes: dict[str, list[str]]):
    """Stands in for the agent: epoch n of a case does its nth outcome, recording what the adapters record.

    An interrupted epoch has completion "" and interrupted True, as the LangGraph adapter leaves it.
    """

    @solver(name="outcomes")
    def outcomes_agent():
        async def solve(state, generate):
            outcome = outcomes[str(state.sample_id)][state.epoch - 1]
            stopped, failed = outcome in (STOPPED, BOTH), outcome in (FAILED, BOTH)
            answer = "" if stopped or failed else outcome
            state.output = ModelOutput.from_content("fake-agent", answer)
            state.metadata["interrupted"] = stopped
            state.metadata["agent_error"] = "RuntimeError: agent failed" if failed else None
            return state

        return solve

    return outcomes_agent()


class CountingJudge:
    """The offline judge double, recording the user prompt of every call it receives."""

    def __init__(self):
        self.model = judge_module.resolve_judge_model(JUDGE_DOUBLE)
        self.prompts: list[str] = []

    async def generate(self, messages):
        self.prompts.append(messages[-1].text)
        return await self.model.generate(messages)

    def answers_judged(self) -> list[str]:
        """The ANSWER (or ANSWER_A/ANSWER_B) block contents of every prompt, in call order."""
        found = []
        for prompt in self.prompts:
            for block in prompt.split("<<<BEGIN ")[1:]:
                name, rest = block.split(" ", 1)
                if name.startswith("ANSWER"):
                    found.append(rest.split(">>>\\n", 1)[1].split("\\n<<<END ", 1)[0])
        return found


@pytest.fixture
def counting(monkeypatch):
    judge_model = CountingJudge()
    monkeypatch.setattr(judge_module, "resolve_judge_model", lambda name: judge_model)
    return judge_model


@pytest.fixture
def evaluate(monkeypatch, tmp_path):
    """Runs {case id: [outcome per epoch]} through build_task and run_task and returns the log path."""

    def run(outcomes, golden=None, baseline=None, capture=False, judge=True):
        monkeypatch.setattr(run_module, "_adapter_solver", lambda adapter, agent, *maps: outcomes_solver(outcomes))
        n = len(list(tmp_path.glob("run*")))
        dataset = tmp_path / f"dataset{n}.jsonl"
        dataset.write_text("\\n".join(json.dumps({"id": i, "input": f"question {i}"}) for i in outcomes), "utf-8")
        golden_path = None
        if golden:
            golden_path = tmp_path / f"golden{n}.jsonl"
            golden_path.write_text("\\n".join(json.dumps({"id": i, "reference": r}) for i, r in golden.items()), "utf-8")
        config = JudgeConfig(JUDGE_DOUBLE, golden_path, None, baseline) if judge else None
        epochs = len(next(iter(outcomes.values())))
        task = build_task(dataset, "unused:agent", capture_content=capture, epochs=epochs, judge_config=config)
        run_dir = tmp_path / f"run{n}"
        run_dir.mkdir()
        return run_task(task, run_dir, capture)

    return run


def judge_scores(log_path: Path) -> dict[str, Score]:
    return {str(s.id): s.scores[JUDGE] for s in read_eval_log(log_path).samples or []}


def verdicts(scores: dict[str, Score]) -> dict[str, tuple]:
    return {i: (s.value, s.metadata.get("mode"), s.metadata.get("not_judged")) for i, s in scores.items()}


# Golden and reference-free


def test_interrupted_cases_pass_not_judged_without_a_judge_call_and_an_agent_error_wins(evaluate, counting):
    # Judged controls (g_ok, r_ok) show the double is reached. Witnesses: "s39 golden interrupted judged" (drop the
    # interrupted return) judges g_int and r_int; "s39 golden interrupted incorrect" scores them I; "s39 golden
    # interrupt before agent error" (agent_error check skipped when interrupted) scores both C as interrupted.
    log_path = evaluate(
        {"g_int": [STOPPED], "g_ok": ["yes"], "r_int": [STOPPED], "r_ok": ["fine"], "both": [BOTH]},
        golden={"g_int": "yes", "g_ok": "yes", "both": "yes"},
    )

    assert verdicts(judge_scores(log_path)) == {
        "both": (INCORRECT, "golden", "agent_error"),
        "g_int": (CORRECT, "golden", INTERRUPTED),
        "g_ok": (CORRECT, "golden", None),
        "r_int": (CORRECT, "reference_free", INTERRUPTED),
        "r_ok": (CORRECT, "reference_free", None),
    }
    assert sorted(counting.answers_judged()) == ["fine", "yes"]


@pytest.mark.parametrize("stopped", [True, False], ids=["interrupted", "answered"])
def test_the_judge_score_is_the_same_with_or_without_interrupts_because_it_reads_interrupted(counting, stopped):
    # The LangGraph adapter stores interrupts only when interrupted; the judge must not depend on that key.
    # Witness: "s49 judge reads interrupts" (judge.py, the golden and reference-free scorer reads "interrupts" for
    # "interrupted") judges the interrupted state that has no interrupts key and skips the answered one that has it.
    score = judge(JUDGE_DOUBLE)

    def scored(extra):
        metadata = {"agent_error": None, "interrupted": stopped, **extra}
        state = TaskState(ModelName("none/none"), "a", 1, "question a", [], metadata=metadata)
        state.output = ModelOutput.from_content("fake-agent", "" if stopped else "fine")
        return asyncio.run(score(state, Target("")))

    without, with_value = scored({}), scored({"interrupts": ["approve?"]})

    assert (with_value.value, with_value.explanation, with_value.metadata) == (
        without.value,
        without.explanation,
        without.metadata,
    )
    assert without.metadata.get("not_judged") == (INTERRUPTED if stopped else None)
    assert counting.answers_judged() == ([] if stopped else ["fine", "fine"])


# Pairwise


def test_pairwise_skips_an_interrupted_case_and_a_case_whose_baseline_only_interrupted(evaluate, counting):
    # c's baseline errored and b's interrupted: each gap keeps its own reason. Only e is judged, once per order.
    # Witnesses: "s39 pairwise interrupted judged" (drop the interrupted return) judges a against its baseline answer;
    # "s39 pairwise interrupted incorrect"; "s39 pairwise interrupt before agent error"; "s39 baseline interrupted gap
    # dropped" (if False) gives b baseline_agent_error.
    baseline = evaluate(
        {"a": ["old a"], "b": [STOPPED], "c": [FAILED], "d": ["old d"], "e": ["old e"]}, capture=True, judge=False
    )
    log_path = evaluate(
        {"a": [STOPPED], "b": ["new b"], "c": ["new c"], "d": [BOTH], "e": ["new e"]}, baseline=baseline.parent
    )

    scores = verdicts(judge_scores(log_path))
    assert {i: (value, reason) for i, (value, _, reason) in scores.items()} == {
        "a": (CORRECT, INTERRUPTED),
        "b": (CORRECT, BASELINE_INTERRUPTED),
        "c": (CORRECT, BASELINE_AGENT_ERROR),
        "d": (INCORRECT, "agent_error"),
        "e": (CORRECT, None),
    }
    assert {mode for _, mode, _ in scores.values()} == {"pairwise"}
    assert sorted(counting.answers_judged()) == ["new e", "new e", "old e", "old e"]


def test_load_baseline_sorts_cases_by_answered_interrupted_and_errored_epochs(evaluate):
    # a and e have an answer in some epoch; b and c never answered but interrupted at least once; d and f never
    # answered nor interrupted (f's interrupted epoch also errored, so it counts as an error).
    # Witnesses: "s39 baseline interrupted epoch answered" (if False) takes b's "" as its answer; "s39 baseline
    # interrupted keeps answered" (interrupted not minus answers) puts a and e in interrupted too; "s39 baseline errored
    # keeps interrupted" puts b and c in errored; "s39 baseline interrupt before error" makes f interrupted.
    log_path = evaluate(
        {
            "a": [STOPPED, "a2"],
            "b": [STOPPED, STOPPED],
            "c": [FAILED, STOPPED],
            "d": [FAILED, FAILED],
            "e": ["e1", STOPPED],
            "f": [BOTH, FAILED],
        },
        capture=True,
        judge=False,
    )

    baseline = load_baseline(log_path)

    assert baseline.answers == {"a": "a2", "e": "e1"}
    assert baseline.interrupted == {"b", "c"}
    assert baseline.errored == {"d", "f"}


# Readings and report


def interrupted_epochs(n: int) -> tuple[JudgedEpoch, ...]:
    return tuple(JudgedEpoch(f"i{k}", "not_judged", "golden", "m", not_judged=INTERRUPTED) for k in range(n))


@pytest.mark.parametrize(
    ("n", "start", "end"),
    [(1, "1 try was not judged", "leaves it out."), (2, "2 tries were not judged", "leaves them out.")],
    ids=["one", "two"],
)
def test_interrupted_tries_get_their_own_reading_in_the_right_number_and_are_not_agent_errors(n, start, end):
    # Witnesses: "s39 readings interrupt number" (== 1 -> == 2) swaps the forms; "s39 readings interrupted as agent
    # errors" (excludes only the baseline gaps) adds the agent error reading.
    epochs = (JudgedEpoch("ok", "pass", "golden", "m"), *interrupted_epochs(n))

    found = judge_readings(epochs, [], 0, None)

    about_interrupts = [r for r in found if "stopped at an interrupt" in r]
    assert [(r.startswith(start), r.endswith(end)) for r in about_interrupts] == [(True, True)]
    assert [r for r in found if "because the agent errored" in r] == []


def judge_bullets(log_path: Path) -> list[str]:
    report = render_run(load_results(log_path)).splitlines()
    section = report[report.index("## Judge") :]
    end = next((i for i in range(1, len(section)) if section[i].startswith("## ")), len(section))
    return [line for line in section[:end] if line.startswith("- Not judged") or line.startswith("- Judged:")]


def test_report_counts_interrupted_cases_apart_from_agent_errors(evaluate):
    # Witnesses: "s39 report interrupted as agent errors" (excludes only the baseline gaps) gives agent error 2; "s39
    # report interrupted count" (== INTERRUPTED -> != INTERRUPTED) miscounts.
    log_path = evaluate({"i": [STOPPED], "e": [FAILED], "ok": ["fine"]})

    assert judge_bullets(log_path) == [
        "- Judged: 1 of 3 cases",
        "- Not judged (agent error): 1",
        "- Not judged (interrupted): 1",
    ]


def test_report_has_no_interrupted_line_when_no_case_interrupted(evaluate):
    # Witness: "s39 report interrupted line always" (if True) adds "- Not judged (interrupted): 0".
    log_path = evaluate({"e": [FAILED], "ok": ["fine"]})

    assert judge_bullets(log_path) == ["- Judged: 1 of 2 cases", "- Not judged (agent error): 1"]
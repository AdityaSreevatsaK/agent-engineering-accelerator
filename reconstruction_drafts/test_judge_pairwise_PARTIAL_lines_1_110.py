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

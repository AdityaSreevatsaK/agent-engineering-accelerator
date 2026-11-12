"""Create a disposable, deterministic Inspect AI evaluation log for unit tests."""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, eval
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.solver import solver

from agent_accelerator.dataset import Case, case_to_metadata
from agent_accelerator.scorers import case_checks


@solver
def calculator_double():
    async def solve(state, generate):
        case_id = str(state.sample_id)
        state.output = ModelOutput.from_content("test-calculator", "5")
        state.metadata["agent_error"] = None
        state.metadata["tool_calls"] = (
            [] if case_id == "no_tool_for_chat"
            else [{"name": "calculator", "arguments": {"left": 9, "right": 4}}]
        )
        state.metadata["tool_errors"] = [] if case_id == "no_tool_for_chat" else [False]
        state.metadata["model_id"] = "unit-test-double"
        state.metadata["usage"] = {"inputTokens": 5, "outputTokens": 2, "totalTokens": 7}
        return state

    return solve


def make_capture(target: Path) -> None:
    """Generate one test log without overwriting an existing file."""
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Refusing to overwrite {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    inputs = (
        ("subtract_nine_four", "What is 9 minus 4?"),
        ("sum_two_three", "What is 2 plus 3?"),
        ("calculator_prompt", "You are a calculator. What is 9 minus 4?"),
        ("multiply", "What is 5 times 1?"),
        ("divide", "What is 10 divided by 2?"),
        ("negative", "What is 1 minus negative 4?"),
        ("decimal", "What is 2.5 plus 2.5?"),
        ("parentheses", "Compute (2+3)."),
        ("tool_error_case", "Calculate 12 minus 7."),
        ("no_tool_for_chat", "Tell me a joke."),
    )
    cases = [
        Case(
            id=name,
            input=question,
            expected_output=None if name == "no_tool_for_chat" else "5",
            expected_tool_calls=[] if name == "no_tool_for_chat" else [
                {"name": "calculator", "arguments": {}, "match": "subset"}
            ],
        )
        for name, question in inputs
    ]
    task = Task(
        name="ci-calculator-double",
        dataset=MemoryDataset(
            [
                Sample(
                    id=case.id,
                    input=case.input,
                    target=case.expected_output or "",
                    metadata=case_to_metadata(case),
                )
                for case in cases
            ],
            name="ci-calculator-double",
        ),
        solver=calculator_double(),
        scorer=case_checks(show_values=True),
    )
    [summary] = eval(
        task,
        model="mockllm/model",
        log_dir=target.parent.as_posix(),
        log_format="json",
        log_realtime=True,
        display="none",
        fail_on_error=False,
    )
    if summary.status != "success":
        raise RuntimeError(f"Local test log failed: {summary.status}")
    log = read_eval_log(summary.location)
    if len(log.samples or []) != 10 or not log.reductions:
        raise AssertionError("The local test log is incomplete")
    if any("case_checks" not in (sample.scores or {}) for sample in log.samples):
        raise AssertionError("A test sample has no score")
    target.write_text(log.model_dump_json(), encoding="utf-8")

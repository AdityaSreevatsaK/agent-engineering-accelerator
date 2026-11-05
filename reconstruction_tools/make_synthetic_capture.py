"""Generate a temporary, SYNTHETIC Inspect capture log solely for CI tests.

This deliberately DOES NOT reconstruct tests/fixtures/calculator_capture_content.json
from historical evidence. The original fixture remains missing. The generated
payloads contain no real user/client data; do not commit the generated JSON.
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, eval
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.solver import solver

from agent_accelerator.dataset import Case, case_to_metadata
from agent_accelerator.scorers import case_checks


SYNTHETIC_CAPTURE = Path("tests/fixtures/calculator_capture_content.json")


@solver
def synthetic_calculator():
    """A deterministic in-process agent double; no external provider used."""

    async def solve(state, generate):
        case_id = str(state.sample_id)
        state.output = ModelOutput.from_content("synthetic-calculator", "5")
        state.metadata["agent_error"] = None
        state.metadata["tool_calls"] = (
            []
            if case_id == "no_tool_for_chat"
            else [{"name": "calculator", "arguments": {"left": 9, "right": 4}}]
        )
        state.metadata["tool_errors"] = [] if case_id == "no_tool_for_chat" else [False]
        state.metadata["model_id"] = "synthetic-only"
        state.metadata["usage"] = {"inputTokens": 5, "outputTokens": 2, "totalTokens": 7}
        return state

    return solve


def synthetic_cases() -> list[Case]:
    inputs = [
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
    ]
    cases = []
    for case_id, question in inputs:
        is_chat = case_id == "no_tool_for_chat"
        cases.append(
            Case(
                id=case_id,
                input=question,
                expected_output=None if is_chat else "5",
                expected_tool_calls=(
                    []
                    if is_chat
                    else [{"name": "calculator", "arguments": {}, "match": "subset"}]
                ),
            )
        )
    return cases


def main() -> None:
    target = Path(__file__).resolve().parents[1] / SYNTHETIC_CAPTURE
    if target.exists():
        raise SystemExit(
            f"Refusing to overwrite {target}. Real/original fixtures must not be replaced."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    cases = synthetic_cases()
    samples = [
        Sample(
            id=case.id,
            input=case.input,
            target=case.expected_output or "",
            metadata=case_to_metadata(case),
        )
        for case in cases
    ]
    task = Task(
        name="CI_SYNTHETIC_CAPTURE_NOT_ORIGINAL",
        dataset=MemoryDataset(samples, name="ci-synthetic-calculator"),
        solver=synthetic_calculator(),
        scorer=case_checks(show_values=True),
    )
    log_dir = target.parent / ".temporary_synthetic_evaluation"
    [summary] = eval(
        task,
        model="mockllm/model",
        log_dir=log_dir.as_posix(),
        log_format="json",
        log_realtime=True,
        display="none",
        fail_on_error=False,
    )
    if summary.status != "success":
        raise RuntimeError(f"Synthetic fixture evaluation failed: {summary.status}")
    log = read_eval_log(summary.location)
    if len(log.samples or []) != 10:
        raise AssertionError("Synthetic fixture should contain exactly ten samples")
    if not (log.reductions or []):
        raise AssertionError("Synthetic fixture must contain scorer reductions")
    if not all("case_checks" in (sample.scores or {}) for sample in log.samples):
        raise AssertionError("Synthetic fixture must contain case_checks for every sample")
    target.write_text(log.model_dump_json(), encoding="utf-8")
    print(
        "Generated temporary SYNTHETIC capture log with ten samples and reductions.",
        "This file is NOT the original calculator_capture_content.json.",
    )


if __name__ == "__main__":
    main()

"""Conformance: each supported LangGraph shape runs end to end through build_task, the real adapter solver, Inspect and
the case checks, offline. One shape also runs through the `aea run` CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.scorer import CORRECT, INCORRECT

from agent_accelerator.compare import load_results
from agent_accelerator.run import build_task, run_task
from agent_accelerator.scorers import CASE_CHECKS

GRAPHS = "aea_conformance_graphs"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

ADDS = {"expected_tool_calls": [{"name": "add", "arguments": {"a": 1, "b": 2}}]}


def evaluate(tmp_path, factory, cases, input_map=None, output_map=None):
    """Runs the cases against the factory with content kept, and returns {case id: sample}."""
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("\n".join(json.dumps(case) for case in cases), encoding="utf-8")
    task = build_task(
        dataset,
        f"{GRAPHS}:{factory}",
        adapter="langgraph",
        capture_content=True,
        input_map=f"{GRAPHS}:{input_map}" if input_map else None,
        output_map=f"{GRAPHS}:{output_map}" if output_map else None,
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log = read_eval_log(run_task(task, run_dir, capture_content=True))
    return {str(s.id): s for s in log.samples or []}


def outcome(sample):
    """What a reader of the run needs: the verdict, the answer, the error and the recorded calls."""
    return {
        "score": sample.scores[CASE_CHECKS].value,
        "completion": sample.output.completion,
        "agent_error": sample.metadata["agent_error"],
        "tool_calls": [call["name"] for call in sample.metadata["tool_calls"]],
    }


def passed(completion, tool_calls=()):
    return {"score": CORRECT, "completion": completion, "agent_error": None, "tool_calls": list(tool_calls)}


@pytest.mark.parametrize(
    ("factory", "case", "expected"),
    [
        # Witness: "s38 lg values only" (stream_mode ["values"]) records no call, so the tool check fails.
        ("messages_react", {"expected_output": "3", **ADDS}, passed("3", ["add"])),
        # Witness: "s38 lg structured_response ignored" answers "3", which fails the schema.
        (
            "create_agent_style",
            {"expected_json_schema": {"required": ["total"], "properties": {"total": {"const": 3}}}, **ADDS},
            passed('{"total":3}', ["add"]),
        ),
        # Witness: "s38 lg no dedupe" lists the worker's add twice, an unexpected extra call.
        (
            "supervisor_with_worker",
            {"output_contains": ["worker says 3"], **ADDS},
            passed("the worker says 3", ["add"]),
        ),
        # Witness: "s38 lg builder not compiled" fails the case as not a local graph.
        ("uncompiled_builder", {"expected_output": "3", **ADDS}, passed("3", ["add"])),
        # Witness: "s38 lg no thread id" fails with LangGraph's missing thread_id error.
        ("with_checkpointer", {"expected_output": "3", **ADDS}, passed("3", ["add"])),
        # Witness: "s38 lg sync stream" (graph.stream) cannot run the async node.
        ("async_only", {"expected_output": "3", **ADDS}, passed("3", ["add"])),
        # Witness: "s38 lg content repr" answers the list's repr.
        ("content_blocks", {"expected_output": "The capital is Paris."}, passed("The capital is Paris.")),
        # Witness: "s38 lg structured dict as repr" answers {'capital': 'Paris'}, which is not JSON.
        (
            "structured_dict",
            {"expected_json_schema": {"properties": {"capital": {"const": "Paris"}}, "required": ["capital"]}},
            passed('{"capital": "Paris"}'),
        ),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_shape_runs_end_to_end_and_passes_its_checks(tmp_path, factory, case, expected):
    samples = evaluate(tmp_path, factory, [{"id": "case", "input": "What is 1 plus 2?", **case}])

    assert outcome(samples["case"]) == expected


def test_custom_state_runs_with_input_and_output_maps(tmp_path):
    # Witnesses: "s38 run maps not passed" (langgraph_agent(agent=agent)) fails both cases naming --input-map; "s38 lg
    # output map ignored" fails them with NoAnswerError.
    cases = [
        {"id": "billing", "input": "I was charged twice", "expected_output": "billing", "expected_tool_calls": []},
        {"id": "technical", "input": "The app crashes on start", "expected_output": "technical"},
    ]

    samples = evaluate(tmp_path, "ticket_triage", cases, input_map="to_ticket", output_map="category_of")

    assert {i: outcome(s) for i, s in samples.items()} == {
        "billing": passed("billing"),
        "technical": passed("technical"),
    }


def test_custom_state_without_an_input_map_fails_each_case_naming_the_flag(tmp_path):
    # Witness: "s38 lg messages channel check dropped" fails it with NoAnswerError instead.
    samples = evaluate(tmp_path, "ticket_triage", [{"id": "a", "input": "I was charged twice"}])

    assert samples["a"].scores[CASE_CHECKS].value == INCORRECT
    assert samples["a"].metadata["agent_error"] == (
        "MissingInputMapError: graph has no 'messages' channel; pass --input-map module:function to build its input"
    )


def test_functional_entrypoint_runs_through_an_input_map(tmp_path):
    # Witness: "s38 lg input map ignored" sends {"messages": ...}, which the entrypoint cannot read.
    case = {"id": "a", "input": "1 plus 2", "expected_output": "1 plus 2 = 3", **ADDS}

    samples = evaluate(tmp_path, "functional", [case], input_map="to_question")

    assert outcome(samples["a"]) == passed("1 plus 2 = 3", ["add"])


def test_an_approval_interrupt_passes_only_the_case_that_expects_it_and_the_gated_tool_never_runs(tmp_path):
    # Witnesses: "s38 lg interrupt not detected" fails both with NoAnswerError; "s38 unexpected interrupt never fails"
    # passes unflagged.
    cases = [
        {"id": "gated", "input": "make user-7 an admin", "expect_interrupt": True, "forbidden_tools": ["grant_admin"]},
        {"id": "unflagged", "input": "make user-7 an admin"},
    ]

    samples = evaluate(tmp_path, "approval_gate", cases)

    assert {i: (outcome(s), s.metadata["interrupted"]) for i, s in samples.items()} == {
        "gated": (passed(""), True),
        "unflagged": ({**passed(""), "score": INCORRECT}, True),
    }
    assert samples["unflagged"].scores[CASE_CHECKS].explanation == "expect_interrupt: unexpected interrupt"


def test_a_graph_that_adds_no_ai_message_fails_the_case_with_no_answer(tmp_path):
    # Witness: "s38 lg last message of any type" answers with the question and records no error.
    samples = evaluate(tmp_path, "adds_no_ai_message", [{"id": "a", "input": "anyone there?"}])

    assert outcome(samples["a"]) == {
        "score": INCORRECT,
        "completion": "",
        "agent_error": "NoAnswerError: no answer produced",
        "tool_calls": [],
    }


@pytest.mark.slow
def test_aea_run_cli_runs_a_custom_state_graph_with_both_maps(tmp_path):
    # A subprocess, as in test_cli.py: the tracer provider can only be set once per process.
    # Witness: "s38 cli maps not passed" (drops input_map and output_map from build_task) fails the case.
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({"id": "a", "input": "I was charged twice", "expected_output": "billing"}), "utf-8")
    command = [sys.executable, "-m", "agent_accelerator.cli", "run", str(dataset), "--adapter", "langgraph"]
    command += ["--agent", f"{GRAPHS}:ticket_triage", "--input-map", f"{GRAPHS}:to_ticket"]
    command += ["--output-map", f"{GRAPHS}:category_of", "--runs-dir", str(tmp_path / "runs")]
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONPATH": os.pathsep.join([str(HERE), os.environ.get("PYTHONPATH", "")]),
    }

    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")

    assert completed.returncode == 0, completed.stderr
    (run_dir,) = (tmp_path / "runs").iterdir()
    assert {case_id: case.passed for case_id, case in load_results(run_dir).cases.items()} == {"a": True}

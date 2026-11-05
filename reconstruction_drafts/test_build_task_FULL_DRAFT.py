import json
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.solver import solver

import agent_accelerator.run as run_module
from agent_accelerator.dataset import DATASET_FORMAT_VERSION, dataset_sha256
from agent_accelerator.run import build_task, run_task

REPO = Path(__file__).parents[2]
DATASET = REPO / "examples" / "calculator" / "dataset.jsonl"
AGENT = "examples.calculator.agent:build_agent"


@pytest.mark.parametrize("epochs", [0, -1])
def test_build_task_rejects_fewer_than_one_epoch(epochs):
    with pytest.raises(ValueError):
        build_task(DATASET, AGENT, "strands", False, epochs=epochs)


def test_build_task_records_requested_epochs_on_the_task_and_its_metadata(monkeypatch):
    # The agent factory is imported from the repo's examples package.
    monkeypatch.syspath_prepend(str(REPO))
    task = build_task(DATASET, AGENT, "strands", False, epochs=3)

    epochs = task.epochs
    assert getattr(epochs, "epochs", epochs) == 3
    assert task.metadata["epochs"] == 3


INPUT_MAP = "examples.triage.agent:to_input"
OUTPUT_MAP = "examples.triage.agent:from_output"


@pytest.fixture
def solver_args(monkeypatch):
    """Replaces the adapter solver, so map references are not imported, and records what build_task passed it."""
    calls = []

    @solver
    def answer_nothing():
        async def solve(state, generate):
            return state

        return solve

    def fake_adapter_solver(adapter, agent, input_map=None, output_map=None):
        calls.append((adapter, agent, input_map, output_map))
        return answer_nothing()

    monkeypatch.setattr(run_module, "_adapter_solver", fake_adapter_solver)
    return calls


def provenance(dataset, adapter, **maps):
    """The task metadata build_task should record, derived from its inputs rather than from a run."""
    return {
        "dataset_path": dataset.as_posix(),
        "dataset_sha256": dataset_sha256(dataset),
        "dataset_format_version": DATASET_FORMAT_VERSION,
        "agent": AGENT,
        "adapter": adapter,
        **maps,
        "epochs": 1,
    }


@pytest.mark.parametrize(
    ("maps", "recorded"),
    [
        ({"input_map": INPUT_MAP, "output_map": OUTPUT_MAP}, {"input_map": INPUT_MAP, "output_map": OUTPUT_MAP}),
        ({"input_map": INPUT_MAP}, {"input_map": INPUT_MAP}),
        ({"output_map": OUTPUT_MAP}, {"output_map": OUTPUT_MAP}),
        ({"input_map": "", "output_map": OUTPUT_MAP}, {"output_map": OUTPUT_MAP}),
        ({"input_map": INPUT_MAP, "output_map": ""}, {"input_map": INPUT_MAP}),
        ({}, {}),
    ],
    ids=["both_maps", "input_map_only", "output_map_only", "empty_input_map_omitted", "empty_output_map_omitted", "no_maps"],
)
def test_build_task_records_each_given_map_reference_as_given_and_omits_the_key_for_one_not_given(
    solver_args, maps, recorded
):
    # The whole metadata dict is compared, so the other provenance keys are pinned as unchanged too.
    # Witnesses (run.py:58–59): s46 run input_map key dropped and s46 run output_map key dropped (line deleted) fail
    # the cases naming that map; s46 run input_map guard dropped (`"input_map": input_map,`) and s46 run output_map
    # guard dropped record None for an absent map; s46 run input_map empty kept (`if input_map is not None`) and s46
    # run output_map empty kept record ""; s46 run maps swapped (`{"input_map": output_map}`) fails both_maps; s46 run
    # output_map guarded on input
    # (`if input_map`) fails input_map_only and output_map_only.
    task = build_task(DATASET, AGENT, "langgraph", False, **maps)

    assert task.metadata == provenance(DATASET, "langgraph", **recorded)
    assert solver_args == [("langgraph", AGENT, maps.get("input_map"), maps.get("output_map"))]


def test_build_task_for_strands_records_neither_map_key_rather_than_none(monkeypatch):
    # The real strands solver is built, so this also proves no map reaches it. Witness s46 run input_map guard dropped
    # (above) records "input_map": None.
    monkeypatch.syspath_prepend(str(REPO))
    task = build_task(DATASET, AGENT, "strands", False)

    assert task.metadata == provenance(DATASET, "strands")
    assert "input_map" not in task.metadata
    assert "output_map" not in task.metadata


def test_run_task_writes_both_map_references_to_the_scrubbed_log_metadata(solver_args, tmp_path):
    # Real Inspect run with mockllm and a solver that answers nothing; the log is the scrubbed copy run_task writes.
    # Witnesses: s46 run input_map key dropped and s46 run output_map key dropped (above) each fail this.
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({"id": "only", "input": "secret question 41"}) + "\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    task = build_task(dataset, AGENT, "langgraph", False, input_map=INPUT_MAP, output_map=OUTPUT_MAP)

    log_path = run_task(task, run_dir, capture_content=False)

    metadata = read_eval_log(log_path).eval.metadata
    assert metadata["input_map"] == INPUT_MAP
    assert metadata["output_map"] == OUTPUT_MAP
    assert {k: metadata.get(k) for k in provenance(dataset, "langgraph")} == provenance(dataset, "langgraph")
    assert "secret question 41" not in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("config", "recorded"),
    [
        pytest.param("conf/aea.toml", {"config": "conf/aea.toml"}, id="relative"),
        pytest.param("C:/work/aea.toml", {"config": "C:/work/aea.toml"}, id="absolute"),
        pytest.param(None, {}, id="no_config"),
    ],
)
def test_build_task_records_the_config_path_exactly_as_given_and_omits_the_key_without_one(
    solver_args, config, recorded
):
    # The whole metadata dict is compared, so no other provenance key moves. Witnesses (run.py:61): s47 run config key
    # dropped (line deleted) fails relative and absolute; s47 run config always emitted (`"config": config,`) fails
    # no_config with "config": None.
    task = build_task(DATASET, AGENT, "langgraph", False, config=config)

    assert task.metadata == provenance(DATASET, "langgraph", **recorded)


def test_build_task_without_an_adapter_argument_builds_and_records_strands(solver_args):
    # Witness: s47 build_task default adapter (`adapter: str = "strands" -> "langgraph"`).
    task = build_task(DATASET, AGENT)

    assert task.metadata["adapter"] == "strands"
    assert [call[0] for call in solver_args] == ["strands"]


def test_run_task_writes_the_config_path_to_the_scrubbed_log_metadata(solver_args, tmp_path):
    # Real Inspect run with mockllm, as in the map test above. Witness: s47 run config key dropped.
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({"id": "only", "input": "a question"}) + "\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    task = build_task(dataset, AGENT, "langgraph", False, config="examples/triage/aea.toml")

    log_path = run_task(task, run_dir, capture_content=False)

    metadata = read_eval_log(log_path).eval.metadata
    assert metadata["config"] == "examples/triage/aea.toml"
    assert {k: metadata.get(k) for k in provenance(dataset, "langgraph")} == provenance(dataset, "langgraph")

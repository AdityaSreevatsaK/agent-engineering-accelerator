import json
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log, write_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.solver import solver

import agent_accelerator.run as run_module
import agent_accelerator.tracing as tracing
from agent_accelerator.cli import EXIT_ERROR, EXIT_OK, build_parser, main
from agent_accelerator.judge import JUDGE, JUDGE_DOUBLE

# In-process `aea run`: the agent answers from a dict and tracing is a no-op, as in test_judge.py's CLI test.
# TODO(PFITAPP-7282): move to tests/conftest.py


class FakeProvider:
    def shutdown(self) -> None:
        pass


def fixed_answers(answers: dict[str, str]):
    @solver(name="fixed_answers")
    def fixed():
        async def solve(state, generate):
            state.output = ModelOutput.from_content("fake-agent", answers[str(state.sample_id)])
            return state

        return solve

    return fixed()


@pytest.fixture
def aea(monkeypatch, tmp_path):
    """Runs `aea` in process with {id: answer} as the agent; returns (exit code, the runs dir's run dirs)."""
    monkeypatch.setattr(tracing, "configure_tracing", lambda path, capture: FakeProvider())

    def run(command: list[str], answers: dict[str, str], runs: Path) -> tuple[int, list[Path]]:
        # Match the run.py positional contract.
        monkeypatch.setattr(
            run_module, "_adapter_solver",
            lambda adapter, agent, input_map=None, output_map=None: fixed_answers(answers),
        )
        code = main([*command, "--agent", "unused:agent", "--runs-dir", str(runs)])
        return code, sorted(runs.iterdir()) if runs.exists() else []

    return run


def dataset(tmp_path: Path, ids=("a", "b"), name="dataset.jsonl") -> Path:
    path = tmp_path / name
    path.write_text("\n".join(json.dumps({"id": i, "input": f"question {i}"}) for i in ids), encoding="utf-8")
    return path


@pytest.fixture
def captured_baseline(aea, tmp_path):
    """A captured run of the dataset with the given answers, made through `aea run --capture-content`."""

    def make(data: Path, answers: dict[str, str]) -> Path:
        code, [run_dir] = aea(["run", str(data), "--capture-content"], answers, tmp_path / "baseline-runs")
        assert code == EXIT_OK
        return run_dir

    return make


def warnings(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("warning:")]


def judge_values(run_dir: Path) -> dict[str, tuple[str, str | None]]:
    log = read_eval_log(next(run_dir.glob("*.json")))
    return {str(s.id): (s.scores[JUDGE].value, s.scores[JUDGE].metadata.get("pairwise")) for s in log.samples}


# Flag checks, before anything runs


def test_judge_baseline_without_judge_exits_2_needing_judge_and_creates_nothing(aea, tmp_path, capsys):
    # Witness: "s33 cli baseline without judge" (drop the baseline from the need --judge check) runs unjudged.
    runs = tmp_path / "runs"

    code, _ = aea(["run", str(dataset(tmp_path)), "--judge-baseline", str(tmp_path)], {"a": "x", "b": "y"}, runs)

    assert code == EXIT_ERROR
    assert "need --judge MODEL" in capsys.readouterr().err
    assert not runs.exists()


def test_golden_with_judge_baseline_exits_2_saying_they_cannot_be_combined(aea, captured_baseline, tmp_path, capsys):
    # The baseline is valid, so only the combination is at fault.
    # Witness: "s33 cli golden and baseline allowed" goes on and fails later inside the scorer with another message.
    data = dataset(tmp_path)
    base = captured_baseline(data, {"a": "x", "b": "y"})
    golden = tmp_path / "g.jsonl"
    golden.write_text(json.dumps({"id": "a", "reference": "x"}), encoding="utf-8")
    runs = tmp_path / "runs"
    command = ["run", str(data), "--judge", JUDGE_DOUBLE, "--golden", str(golden), "--judge-baseline", str(base)]

    code, _ = aea(command, {"a": "x", "b": "y"}, runs)

    assert code == EXIT_ERROR
    assert "cannot be combined" in capsys.readouterr().err
    assert not runs.exists()


@pytest.mark.parametrize("command", ["run", "check"])
def test_a_scrubbed_baseline_exits_2_before_any_run_directory_exists(aea, tmp_path, capsys, command):
    # A baseline run without --capture-content. check's own --baseline exists, so only the judge baseline fails.
    # Witness: "s33 cli baseline checked late" (drop the early check) creates the runs dir before the scorer fails.
    data = dataset(tmp_path)
    code, [scrubbed] = aea(["run", str(data)], {"a": "x", "b": "y"}, tmp_path / "baseline-runs")
    assert code == EXIT_OK
    check_baseline = tmp_path / "check-baseline"
    check_baseline.mkdir()
    extra = ["--baseline", str(check_baseline)] if command == "check" else []
    runs = tmp_path / "runs"

    code, _ = aea([command, str(data), *extra, "--judge", JUDGE_DOUBLE, "--judge-baseline", str(scrubbed)], {}, runs)

    assert code == EXIT_ERROR
    assert "--capture-content" in capsys.readouterr().err
    assert not runs.exists()


# A pairwise run, and the dataset check


def test_a_pairwise_run_on_the_baselines_dataset_warns_nothing_and_records_the_baseline(
    aea, captured_baseline, tmp_path, capsys
):
    # Witness: "s33 cli config drops baseline" (JudgeConfig without baseline_path) judges reference-free instead.
    data = dataset(tmp_path)
    base = captured_baseline(data, {"a": "same answer", "b": "old"})
    capsys.readouterr()

    code, [run_dir] = aea(
        ["run", str(data), "--judge", JUDGE_DOUBLE, "--judge-baseline", str(base)],
        {"a": "same answer", "b": ""},
        tmp_path / "runs",
    )

    assert code == EXIT_OK
    assert warnings(capsys.readouterr().err) == []
    assert judge_values(run_dir) == {"a": ("C", "same"), "b": ("I", "worse")}
    provenance = read_eval_log(next(run_dir.glob("*.json"))).eval.metadata["judge"]
    assert (provenance["mode"], provenance["baseline_run_id"]) == ("pairwise", base.name)


def edit_dataset_hash(base: Path, tmp_path: Path, value: str) -> Path:
    """A copy of the baseline log whose recorded dataset hash is value; everything else, answers included, is kept."""
    log = read_eval_log(next(base.glob("*.json")))
    log.eval.metadata = {**log.eval.metadata, "dataset_sha256": value}
    path = tmp_path / "edited-baseline.json"
    write_eval_log(log, path.as_posix())
    return path


@pytest.mark.parametrize("command", ["run", "check"])
def test_a_baseline_from_another_dataset_warns_once_and_the_run_and_its_verdicts_are_unchanged(
    aea, captured_baseline, tmp_path, capsys, command
):
    # The same baseline answers twice: once as recorded, once claiming another dataset. Only the warning differs.
    # Witnesses: "s33 cli warning not printed" prints nothing; "s33 cli warning raises" (a mismatch is an error)
    # exits 2; "s33 cli dataset not compared" (compare against the baseline's own hash) prints nothing.
    data = dataset(tmp_path)
    answers = {"a": "same answer", "b": "old"}
    base = captured_baseline(data, answers)
    edited = edit_dataset_hash(base, tmp_path, "0" * 64)
    capsys.readouterr()
    check_baseline = tmp_path / "check-baseline"
    extra = ["--baseline", str(check_baseline), "--update-baseline"] if command == "check" else []
    new = {"a": "same answer.", "b": ""}

    code, [matched] = aea(
        [command, str(data), *extra, "--judge", JUDGE_DOUBLE, "--judge-baseline", str(base)],
        new,
        tmp_path / "runs-matched",
    )
    quiet = warnings(capsys.readouterr().err)
    code_edited, [mismatched] = aea(
        [command, str(data), *extra, "--judge", JUDGE_DOUBLE, "--judge-baseline", str(edited)],
        new,
        tmp_path / "runs-mismatched",
    )
    [warning] = warnings(capsys.readouterr().err)

    assert (code, code_edited, quiet) == (EXIT_OK, EXIT_OK, [])
    assert "0" * 12 in warning and "may not be comparable" in warning
    assert judge_values(mismatched) == judge_values(matched) == {"a": ("C", "same"), "b": ("I", "worse")}


@pytest.mark.parametrize("command", [["run"], ["check", "--baseline", "base"]], ids=["run", "check"])
def test_judge_baseline_parses_on_run_and_check_and_defaults_to_none(command):
    # Witness: "s33 cli baseline flag dropped" removes the flag, so parsing exits.
    with_flag = build_parser().parse_args(
        [command[0], "d.jsonl", "--agent", "m:f", *command[1:], "--judge-baseline", "b"]
    )
    without = build_parser().parse_args([command[0], "d.jsonl", "--agent", "m:f", *command[1:]])

    assert (with_flag.judge_baseline, without.judge_baseline) == (Path("b"), None)

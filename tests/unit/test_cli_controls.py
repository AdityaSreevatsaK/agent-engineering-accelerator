"""Verify command-line flags, configuration precedence and input validation."""

import sys
from pathlib import Path

import pytest

from agent_accelerator import cli


class StopBeforeRun(Exception):
    """Stop immediately after the real CLI has merged and validated flags."""


@pytest.fixture
def seen(monkeypatch):
    captured = []

    def stop(args):
        captured.append(vars(args).copy())
        raise StopBeforeRun

    monkeypatch.setattr(cli, "_execute_run", stop)
    monkeypatch.setattr(sys, "path", list(sys.path))
    return captured


def command_args(command, tmp_path, *settings):
    common = [command, "unused.jsonl", "--runs-dir", str(tmp_path / "runs")]
    if command == "check":
        common += ["--baseline", str(tmp_path / "baseline"), "--update-baseline"]
    return [*common, *settings]


def write_config(tmp_path, **values):
    path = tmp_path / "aea.toml"
    path.write_text("".join(f'{key} = "{value}"\n' for key, value in values.items()), encoding="utf-8")
    return path


@pytest.mark.parametrize("command", ["run", "check"])
def test_default_adapter_is_strands_in_both_run_commands(seen, tmp_path, command):
    with pytest.raises(StopBeforeRun):
        cli.main(command_args(command, tmp_path, "--agent", "test:factory"))
    assert len(seen) == 1
    assert seen[0]["adapter"] == "strands"
    assert seen[0]["epochs"] == 1
    assert seen[0]["capture_content"] is False
    assert seen[0]["max_samples"] is None


@pytest.mark.parametrize("command", ["run", "check"])
def test_config_fills_unspecified_adapter_agent_and_maps(seen, tmp_path, command):
    config = write_config(
        tmp_path,
        adapter="langgraph",
        agent="cfg:factory",
        input_map="cfg:to_input",
        output_map="cfg:from_output",
    )
    with pytest.raises(StopBeforeRun):
        cli.main(command_args(command, tmp_path, "--config", str(config)))
    assert len(seen) == 1
    for name, value in {
        "adapter": "langgraph",
        "agent": "cfg:factory",
        "input_map": "cfg:to_input",
        "output_map": "cfg:from_output",
    }.items():
        assert seen[0][name] == value


@pytest.mark.parametrize("command", ["run", "check"])
def test_explicit_flags_override_conflicting_config_values(seen, tmp_path, command):
    config = write_config(
        tmp_path,
        adapter="langgraph",
        agent="cfg:factory",
        input_map="cfg:to_input",
        output_map="cfg:from_output",
    )
    with pytest.raises(StopBeforeRun):
        cli.main(command_args(
            command,
            tmp_path,
            "--config", str(config),
            "--agent", "flag:factory",
            "--input-map", "flag:to_input",
            "--output-map", "flag:from_output",
        ))
    assert seen[0]["agent"] == "flag:factory"
    assert seen[0]["input_map"] == "flag:to_input"
    assert seen[0]["output_map"] == "flag:from_output"
    assert seen[0]["adapter"] == "langgraph"


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize("with_config", [False, True])
def test_missing_agent_is_usage_error_before_launch(seen, tmp_path, capsys, command, with_config):
    args = command_args(command, tmp_path)
    if with_config:
        config = write_config(tmp_path, adapter="langgraph")
        args.extend(["--config", str(config)])
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
    assert "--agent is required" in capsys.readouterr().err
    assert seen == []


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize("adapter", ["Strands", "openai"])
def test_non_supported_adapter_choice_is_parser_error(command, adapter, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(command_args(command, tmp_path, "--agent", "x:y", "--adapter", adapter))
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["compare", "check"])
@pytest.mark.parametrize("value", ["0.05", "1e-3", "0.999"])
def test_significance_threshold_accepts_open_unit_interval(command, value, tmp_path):
    args = ["compare", "baseline", "current"] if command == "compare" else command_args(command, tmp_path, "--agent", "x:y")
    parsed = cli.build_parser().parse_args([*args, "--max-p-value", value])
    assert parsed.max_p_value == float(value)


@pytest.mark.parametrize("command", ["compare", "check"])
@pytest.mark.parametrize("value", ["abc", "0", "1"])
def test_invalid_significance_threshold_is_usage_error(command, value, tmp_path, capsys):
    args = ["compare", "baseline", "current"] if command == "compare" else command_args(command, tmp_path, "--agent", "x:y")
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args([*args, "--max-p-value", value])
    assert exc.value.code == 2
    assert "--max-p-value" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize("config_maps", [False, True])
def test_maps_require_langgraph_even_when_config_supplies_them(seen, tmp_path, capsys, command, config_maps):
    if config_maps:
        config = write_config(tmp_path, agent="cfg:factory", input_map="cfg:to_input")
        args = ["--config", str(config)]
    else:
        args = ["--agent", "flag:factory", "--input-map", "flag:to_input"]
    with pytest.raises(SystemExit) as exc:
        cli.main(command_args(command, tmp_path, *args))
    assert exc.value.code == 2
    assert "need --adapter langgraph" in capsys.readouterr().err
    assert seen == []


@pytest.mark.parametrize("command,extra", [
    ("compare", ["b", "c"]), ("report", ["r"]),
    ("init", ["a"]), ("export", ["a.md"]),
])
def test_non_run_commands_do_not_accept_config(command, extra, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args([command, *extra, "--config", "aea.toml"])
    assert exc.value.code == 2
    assert "unrecognized arguments: --config" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "check"])
def test_nearby_config_is_not_implicitly_loaded(seen, tmp_path, monkeypatch, command):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, adapter="langgraph", agent="cfg:factory")
    with pytest.raises(StopBeforeRun):
        cli.main(command_args(command, tmp_path, "--agent", "flag:factory"))
    assert seen[0]["adapter"] == "strands"
    assert seen[0]["agent"] == "flag:factory"
    assert seen[0]["config"] is None



@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize(
    ("content", "error_text"),
    [
        (b'model = "gpt"\n', "unknown key 'model'"),
        (b'agent = "caf\xff:build_agent"\n', "utf-8"),
    ],
    ids=["unknown_key", "invalid_utf8"],
)
def test_config_errors_are_reported_before_any_run(seen, tmp_path, capsys, command, content, error_text):
    """Ensure invalid configuration is rejected before agent execution."""
    config = tmp_path / "aea.toml"
    config.write_bytes(content)
    args = command_args(command, tmp_path, "--config", str(config), "--agent", "flag:factory")

    assert cli.main(args) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert config.as_posix() in err
    assert error_text in err.lower()
    assert "Traceback" not in err
    assert seen == []
    assert not (tmp_path / "runs").exists()


def test_check_missing_baseline_does_not_launch_agent(seen, tmp_path, capsys):
    """Missing baseline is an early error unless the user requests a freeze."""
    missing = tmp_path / "missing"
    args = [
        "check", "unused.jsonl", "--agent", "flag:factory",
        "--runs-dir", str(tmp_path / "runs"), "--baseline", str(missing),
    ]
    assert cli.main(args) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert "no baseline at" in err and "--update-baseline" in err
    assert seen == []
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        (["--capture-content"], "--capture-content"),
        (["--runs-dir", "BASELINE"], "contains --runs-dir"),
    ],
    ids=["captured_content", "runs_inside_baseline"],
)
def test_freeze_refuses_unsafe_target_before_agent_start(seen, tmp_path, capsys, extra, reason):
    """No captured content or recursive run paths may enter baseline snapshots."""
    baseline = tmp_path / "baseline"
    expanded_extra = [str(baseline) if x == "BASELINE" else x for x in extra]
    args = [
        "check", "unused.jsonl", "--agent", "flag:factory",
        "--runs-dir", str(tmp_path / "runs"), "--baseline", str(baseline),
        "--update-baseline", *expanded_extra,
    ]
    assert cli.main(args) == cli.EXIT_ERROR
    assert reason in capsys.readouterr().err
    assert seen == []
    assert not baseline.exists()


@pytest.mark.parametrize("command", ["compare", "check"])
def test_threshold_flags_have_expected_defaults(command, tmp_path):
    """Parser defaults are part of the public CLI contract."""
    args = (
        ["compare", "baseline", "current"]
        if command == "compare"
        else command_args(command, tmp_path, "--agent", "flag:factory")
    )
    parsed = cli.build_parser().parse_args(args)
    expected = {
        "max_new_failures": 0,
        "max_pass_rate_drop": 0.0,
        "max_error_rate_increase": 0.0,
        "min_case_pass_rate": 1.0,
        "max_p_value": None,
    }
    assert {key: getattr(parsed, key) for key in expected} == expected


@pytest.mark.parametrize(
    "check_flags",
    [
        ("--baseline", "absent"),
        ("--baseline", "absent", "--update-baseline", "--capture-content"),
    ],
    ids=["missing_baseline", "unsafe_captured_baseline"],
)
def test_bad_config_is_rejected_before_check_baseline_validation(
    seen, tmp_path, capsys, check_flags
):
    """Invalid configuration takes priority over baseline validation."""
    config = tmp_path / "aea.toml"
    config.write_text('model = "gpt"\n', encoding="utf-8")
    args = [
        "check", "unused.jsonl", "--agent", "flag:factory",
        "--runs-dir", str(tmp_path / "runs"),
        "--config", str(config), *check_flags,
    ]

    assert cli.main(args) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert f"{config.as_posix()}: unknown key 'model'" in err
    assert "--update-baseline cannot be combined" not in err
    assert "no baseline at" not in err
    assert seen == []
    assert not (tmp_path / "runs").exists()



@pytest.mark.parametrize("command", ["compare", "check"])
@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--max-new-failures", "-1"),
        ("--max-new-failures", "1.5"),
        ("--max-pass-rate-drop", "-0.01"),
        ("--max-pass-rate-drop", "1.01"),
        ("--max-pass-rate-drop", "nan"),
        ("--max-pass-rate-drop", "inf"),
        ("--max-error-rate-increase", "-0.1"),
        ("--max-error-rate-increase", "1.1"),
        ("--max-error-rate-increase", "nan"),
        ("--min-case-pass-rate", "0"),
        ("--min-case-pass-rate", "-0.1"),
        ("--min-case-pass-rate", "1.1"),
        ("--min-case-pass-rate", "nan"),
        ("--min-case-pass-rate", "inf"),
    ],
)
def test_invalid_quality_gate_flags_fail_before_execution(command, flag, value, tmp_path, capsys):
    args = (
        ["compare", "baseline", "current"]
        if command == "compare"
        else command_args(command, tmp_path, "--agent", "test:factory")
    )
    with pytest.raises(SystemExit) as error:
        cli.build_parser().parse_args([*args, flag, value])
    assert error.value.code == 2
    assert flag in capsys.readouterr().err


@pytest.mark.parametrize("command", ["compare", "check"])
@pytest.mark.parametrize(
    ("flag", "value", "expected"),
    [
        ("--max-new-failures", "0", 0),
        ("--max-new-failures", "10", 10),
        ("--max-pass-rate-drop", "0", 0.0),
        ("--max-pass-rate-drop", "1", 1.0),
        ("--max-error-rate-increase", "0", 0.0),
        ("--max-error-rate-increase", "1", 1.0),
        ("--min-case-pass-rate", "0.25", 0.25),
        ("--min-case-pass-rate", "1", 1.0),
    ],
)
def test_valid_quality_gate_boundaries_remain_supported(command, flag, value, expected, tmp_path):
    args = (
        ["compare", "baseline", "current"]
        if command == "compare"
        else command_args(command, tmp_path, "--agent", "test:factory")
    )
    parsed = cli.build_parser().parse_args([*args, flag, value])
    assert getattr(parsed, flag.removeprefix("--").replace("-", "_")) == expected

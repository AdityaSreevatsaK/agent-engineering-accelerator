"""Preflight CLI contracts: safe defaults, imported references and useful onboarding errors."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent_accelerator import cli


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, "path", list(sys.path))
    (tmp_path / "doctor_example.py").write_text(
        "def build_agent():\n"
        "    raise AssertionError('agent factory must never be executed during preflight')\n"
        "def to_input(question):\n"
        "    return {'question': question}\n"
        "def to_output(state):\n"
        "    return str(state)\n"
        "def scorer():\n"
        "    raise AssertionError('scorer must never be executed during preflight')\n",
        encoding="utf-8",
    )
    (tmp_path / "dataset.jsonl").write_text(
        '{"id": "case-1", "input": "synthetic question", "expected_output": "synthetic answer"}\n',
        encoding="utf-8",
    )
    return tmp_path


def test_doctor_checks_imports_and_dataset_without_running_agent_or_creating_runs(project, capsys):
    args = [
        "doctor", "dataset.jsonl", "--adapter", "langgraph",
        "--agent", "doctor_example:build_agent",
        "--input-map", "doctor_example:to_input",
        "--output-map", "doctor_example:to_output",
        "--scorer", "doctor_example:scorer",
    ]
    assert cli.main(args) == cli.EXIT_OK
    output = capsys.readouterr()
    assert "OK dataset: 1 valid case(s); adapter: langgraph" in output.out
    assert "PASS: preflight complete" in output.out
    assert "no agent factory, evaluation, or model was executed" in output.out
    assert not output.err
    assert not (project / "runs").exists()


def test_doctor_loads_config_and_explains_when_langgraph_mappers_may_be_required(project, capsys):
    config = project / "aea.toml"
    config.write_text('adapter = "langgraph"\nagent = "doctor_example:build_agent"\n', encoding="utf-8")
    assert cli.main(["doctor", "dataset.jsonl", "--config", str(config)]) == cli.EXIT_OK
    found = capsys.readouterr()
    assert "OK agent: doctor_example:build_agent" in found.out
    assert "--input-map module:function" in found.err
    assert "--output-map module:function" in found.err


def test_doctor_reports_misspelt_application_module_without_creating_run_directory(project, capsys):
    code = cli.main(["doctor", "dataset.jsonl", "--agent", "missing_aea_doctor_mod:build_agent"])
    assert code == cli.EXIT_ERROR
    assert "working directory and module path" in capsys.readouterr().err
    assert not (project / "runs").exists()


def test_doctor_rejects_invalid_dataset_before_importing_agent(project, capsys):
    bad = project / "invalid.jsonl"
    bad.write_text('{"id":"same","input":"q"}\n{"id":"same","input":"q2"}\n', encoding="utf-8")
    result = cli.main(["doctor", str(bad), "--agent", "missing_aea_doctor_mod:build_agent"])
    assert result == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert "duplicate case ids" in err
    assert "cannot import module" not in err
    assert not (project / "runs").exists()


def test_doctor_cli_flags_override_config_without_executing_agent(project, capsys):
    config = project / "aea.toml"
    config.write_text('agent = "missing_aea_doctor_mod:build_agent"\n', encoding="utf-8")
    assert cli.main([
        "doctor", "dataset.jsonl", "--config", str(config),
        "--agent", "doctor_example:build_agent",
    ]) == cli.EXIT_OK
    assert "OK agent: doctor_example:build_agent" in capsys.readouterr().out


def test_doctor_rejects_wrong_adapter_for_mapper_before_any_import(project, capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main([
            "doctor", "dataset.jsonl", "--agent", "doctor_example:build_agent",
            "--adapter", "strands", "--input-map", "doctor_example:to_input",
        ])
    assert caught.value.code == 2
    assert "--adapter langgraph" in capsys.readouterr().err
    assert not (project / "runs").exists()

"""Fail early and clearly for invalid agent, mapper and custom scorer references."""

from pathlib import Path

import pytest

from agent_accelerator import cli
from agent_accelerator.adapters import load_factory, validate_factory_reference


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("agent:build_agent", ("agent", "build_agent")),
        ("package.agents:factory", ("package.agents", "factory")),
        ("integrations.vendor_langgraph.agent:to_request", ("integrations.vendor_langgraph.agent", "to_request")),
    ],
)
def test_reference_validation_accepts_documented_syntax_without_importing(reference, expected):
    assert validate_factory_reference(reference) == expected


@pytest.mark.parametrize(
    "reference",
    [
        "", "agent", "agent:", ":build_agent", "agent:fn:extra",
        ".agents:build", "package.:build", "bad-name.agent:factory",
        "package.agent:bad-name", "class.agent:factory", "package.agent:for",
        "package.agent:method.name",
    ],
)
def test_reference_validation_rejects_malformed_syntax(reference):
    with pytest.raises(ValueError, match="module:function"):
        validate_factory_reference(reference)


def test_missing_application_module_error_explains_working_directory():
    with pytest.raises(ModuleNotFoundError, match="working directory and module path") as error:
        load_factory("this_aea_module_does_not_exist:build_agent")
    assert error.value.name == "this_aea_module_does_not_exist"


def test_missing_dependency_inside_existing_module_is_not_misreported(monkeypatch):
    from agent_accelerator import adapters

    def missing_dependency(module_name):
        raise ModuleNotFoundError("No module named 'optional_framework'", name="optional_framework")

    monkeypatch.setattr(adapters.importlib, "import_module", missing_dependency)
    with pytest.raises(ModuleNotFoundError) as error:
        load_factory("legitimate.agent:build_agent")
    assert error.value.name == "optional_framework"


def test_missing_attribute_and_noncallable_attribute_are_reported():
    with pytest.raises(ValueError, match="has no attribute"):
        load_factory("math:does_not_exist")
    with pytest.raises(ValueError, match="not callable"):
        load_factory("math:pi")


@pytest.mark.parametrize(
    ("flag", "invalid"),
    [
        ("--agent", "package:build:bad"),
        ("--agent", "package.:build"),
        ("--input-map", "mapper:bad:extra"),
        ("--output-map", "mapper:no-name!"),
        ("--scorer", "score:bad:extra"),
    ],
)
def test_cli_rejects_bad_references_before_any_run_directory(tmp_path: Path, capsys, flag, invalid):
    settings = ["run", "missing.jsonl", "--adapter", "langgraph", "--agent", "package:build"]
    settings += [flag, invalid, "--runs-dir", str(tmp_path / "runs")]
    assert cli.main(settings) == cli.EXIT_ERROR
    stderr = capsys.readouterr().err
    assert "module:function" in stderr
    assert "Traceback" not in stderr
    assert not (tmp_path / "runs").exists()


def test_cli_rejects_bad_config_reference_before_run(tmp_path: Path, capsys):
    config = tmp_path / "aea.toml"
    config.write_text('adapter = "strands"\nagent = "package:factory:extra"\n', encoding="utf-8")
    assert cli.main(
        ["run", "missing.jsonl", "--config", str(config), "--runs-dir", str(tmp_path / "runs")]
    ) == cli.EXIT_ERROR
    assert "--agent:" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()

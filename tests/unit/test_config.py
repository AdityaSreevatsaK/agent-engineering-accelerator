import tomllib
from pathlib import Path

import pytest

import agent_accelerator.config as config_module
from agent_accelerator.adapters import load_factory
from agent_accelerator.config import ConfigError, load_config

REPO = Path(__file__).parents[2]
ALLOWED = "adapter, agent, input_map, output_map"
FULL = {
    "adapter": "langgraph",
    "agent": "pkg.agent:build_agent",
    "input_map": "pkg.agent:to_input",
    "output_map": "pkg.agent:from_output",
}


def write_config(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def toml_line(key, value):
    return f'{key} = "{value}"\n'


# returns


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param(FULL, id="all_four_keys"),
        pytest.param({"agent": FULL["agent"]}, id="agent_only"),
        pytest.param({"adapter": "strands", "output_map": FULL["output_map"]}, id="adapter_and_output_map"),
    ],
)
def test_load_config_returns_exactly_the_keys_the_file_sets_with_their_values(tmp_path, settings):
    # Witness s47 config absent keys as None (`return dict(data)` -> one entry per CONFIG_KEYS with .get) fails
    # agent_only and adapter_and_output_map.
    path = write_config(tmp_path / "aea.toml", "".join(toml_line(k, v) for k, v in settings.items()))

    assert load_config(path) == settings


def test_load_config_of_an_empty_file_or_one_with_only_comments_is_an_empty_dict(tmp_path):
    # Witness: s47 config absent keys as None (above) returns four None entries for each.
    empty = write_config(tmp_path / "empty.toml", "")
    comments = write_config(tmp_path / "comments.toml", "# flags on the command line win\n\n")

    assert load_config(empty) == {}
    assert load_config(comments) == {}


# unreadable files


def test_load_config_of_a_missing_file_says_file_not_found_after_the_posix_path(tmp_path):
    # Witnesses: s47 config file not found branch dropped (the OSError branch then says "No such file or directory");
    # s47 config path prefix empty (`shown = ""`); s47 config path not posix (`shown = str(path)`, Windows only).
    path = tmp_path / "absent" / "aea.toml"

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: file not found"


def test_config_error_is_a_value_error_so_callers_catching_value_error_still_catch_it(tmp_path):
    # Witness: s47 config error not a ValueError (`class ConfigError(Exception)`).
    with pytest.raises(ValueError, match="file not found"):
        load_config(tmp_path / "absent.toml")


def test_load_config_of_a_directory_reports_the_os_reason_after_the_path(tmp_path):
    # The reason is whatever this OS gives for opening a directory (Windows: permission denied, POSIX: is a directory),
    # read from the OS here rather than written down. Witness: s47 config OSError branch dropped (the OSError escapes).
    folder = tmp_path / "aea.toml"
    folder.mkdir()
    with pytest.raises(OSError) as os_error:
        open(folder, "rb")  # noqa: SIM115

    with pytest.raises(ConfigError) as exc:
        load_config(folder)

    assert str(exc.value) == f"{folder.as_posix()}: {os_error.value.strerror}"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        pytest.param(OSError(5, "Input/output error"), "Input/output error", id="with_strerror"),
        pytest.param(OSError("device went away"), "device went away", id="without_strerror"),
    ],
)
def test_load_config_reports_another_os_error_by_its_reason_without_chaining_it(tmp_path, monkeypatch, error, reason):
    # `open` is shadowed in the config module only, since no real file fails this way on demand.
    # Witnesses: s47 config OSError branch dropped fails both; s47 config strerror without fallback
    # (`exc.strerror`) fails without_strerror with "None".
    def failing_open(*args, **kwargs):
        raise error

    monkeypatch.setattr(config_module, "open", failing_open, raising=False)
    path = tmp_path / "aea.toml"

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: {reason}"
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__ is True


def test_load_config_of_invalid_toml_reports_the_parser_message_after_the_path(tmp_path):
    # Witness: s47 config TOML decode branch dropped (tomllib.TOMLDecodeError escapes, not a ConfigError).
    text = 'agent = "pkg.agent:build_agent\n'  # unterminated string
    with pytest.raises(tomllib.TOMLDecodeError) as decode_error:
        tomllib.loads(text)
    path = write_config(tmp_path / "aea.toml", text)

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: {decode_error.value}"


def test_load_config_of_a_non_utf8_file_reports_the_decoder_message_after_the_path_without_chaining_it(tmp_path):
    # TOML is UTF-8 only, so the byte 0xff is a decode error; the message is read from the decoder, not written down.
    # Witness: s48 config UnicodeDecodeError not caught (`except (tomllib.TOMLDecodeError, UnicodeDecodeError)` ->
    # `except tomllib.TOMLDecodeError`) lets the UnicodeDecodeError escape.
    content = b'agent = "caf\xff:build_agent"\n'
    with pytest.raises(UnicodeDecodeError) as decode_error:
        content.decode("utf-8")
    path = tmp_path / "aea.toml"
    path.write_bytes(content)

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: {decode_error.value}"
    assert isinstance(exc.value, ValueError)
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__ is True


# invalid content


def test_load_config_rejects_an_unknown_key_naming_it_and_listing_the_allowed_keys(tmp_path):
    # Witnesses: s47 config unknown key accepted (`if key not in CONFIG_KEYS:` -> `if False:`); s47 config path prefix
    # empty.
    path = write_config(tmp_path / "aea.toml", toml_line("agent", FULL["agent"]) + toml_line("model", "gpt"))

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: unknown key 'model'; allowed: {ALLOWED}"


@pytest.mark.parametrize(
    ("line", "key", "type_name"),
    [
        pytest.param("adapter = 1\n", "adapter", "int", id="int_adapter"),
        pytest.param('agent = ["pkg.agent:build_agent"]\n', "agent", "list", id="list_agent"),
        pytest.param('[input_map]\nmodule = "pkg.agent"\n', "input_map", "dict", id="table_input_map"),
        pytest.param("output_map = true\n", "output_map", "bool", id="bool_output_map"),
    ],
)
def test_load_config_rejects_a_non_string_value_naming_the_key_and_its_type(tmp_path, line, key, type_name):
    # A TOML table is reported by its Python type name, "dict" (characterisation: pins current wording).
    # Witness: s47 config non-string accepted (`if not isinstance(value, str):` -> `if False:`) fails every id
    # (int_adapter with the adapter message, the others with a TypeError on the ":" test).
    path = write_config(tmp_path / "aea.toml", line)

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: {key} must be a string, got {type_name}"


@pytest.mark.parametrize("adapter", ["Strands", "LangGraph", "openai", ""])
def test_load_config_rejects_an_adapter_other_than_strands_or_langgraph_case_sensitively(tmp_path, adapter):
    # Witness: s47 config adapter unchecked (`if "adapter" in data and ...` -> `if False:`).
    path = write_config(tmp_path / "aea.toml", toml_line("adapter", adapter))

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: adapter must be one of strands, langgraph, got {adapter!r}"


@pytest.mark.parametrize("key", ["agent", "input_map", "output_map"])
@pytest.mark.parametrize("ref", ["pkg.agent.build_agent", ""], ids=["dotted", "empty"])
def test_load_config_rejects_a_reference_without_a_colon_naming_the_key(tmp_path, key, ref):
    # Witnesses: s47 config ref colon unchecked (`if key in data and ":" not in data[key]:` -> `if False:`) fails every
    # id; s47 config only agent ref checked (`_REF_KEYS = ("agent",)`) fails the input_map and output_map ids.
    path = write_config(tmp_path / "aea.toml", toml_line(key, ref))

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert str(exc.value) == f"{path.as_posix()}: {key} must be module:function, got {ref!r}"


# shipped examples


@pytest.mark.parametrize("example", ["triage", "expense"])
def test_example_config_loads_and_every_reference_it_names_resolves_to_a_callable(monkeypatch, example):
    # The examples package is imported from the repo root, as `aea run` does from the working directory.
    # Witnesses: s47 triage config input_map ref broken and s47 expense config agent ref broken (an attribute the
    # example module does not have) fail that id.
    monkeypatch.syspath_prepend(str(REPO))
    config = load_config(REPO / "examples" / example / "aea.toml")
    refs = {key: config[key] for key in ("agent", "input_map", "output_map") if key in config}

    assert "agent" in refs
    for ref in refs.values():
        assert callable(load_factory(ref))


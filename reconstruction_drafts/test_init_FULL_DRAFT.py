from importlib.resources import files

import pytest

from agent_accelerator.cli import main

TEMPLATE_NAMES = ("agent.py", "dataset.jsonl")
PLACEHOLDER = "--agent <module>.agent:build_agent"


def template_text(name):
    return (files("agent_accelerator") / "template" / name).read_text(encoding="utf-8")


def assert_matches_template(folder):
    for name in TEMPLATE_NAMES:
        assert (folder / name).read_text(encoding="utf-8") == template_text(name), name


def run_line(out):
    [line] = [line for line in out.splitlines() if "uv run aea run" in line]
    return line[line.index("uv run aea run") :].rstrip()


# fresh and empty folders


def test_init_fresh_nested_dir_writes_template_files_and_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert main(["init", "agents/my_bot"]) == 0

    folder = tmp_path / "agents" / "my_bot"
    assert sorted(p.name for p in folder.iterdir()) == sorted(TEMPLATE_NAMES)
    assert_matches_template(folder)


def test_init_from_unrelated_cwd_with_absolute_dir_writes_template_files(tmp_path, monkeypatch, capsys):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    target = tmp_path / "out" / "bot"

    assert main(["init", str(target)]) == 0

    assert_matches_template(target)
    assert list(elsewhere.iterdir()) == []


def test_init_existing_empty_dir_is_accepted_without_force(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bot").mkdir()

    assert main(["init", "bot"]) == 0

    assert_matches_template(tmp_path / "bot")


# non-empty folders and --force


def test_init_non_empty_dir_without_force_exits_two_and_touches_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "bot"
    folder.mkdir()
    (folder / "agent.py").write_text("mine\\n", encoding="utf-8")
    (folder / "notes.txt").write_text("keep\\n", encoding="utf-8")

    assert main(["init", "bot"]) == 2

    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "--force" in err
    assert sorted(p.name for p in folder.iterdir()) == ["agent.py", "notes.txt"]
    assert (folder / "agent.py").read_text(encoding="utf-8") == "mine\\n"
    assert (folder / "notes.txt").read_text(encoding="utf-8") == "keep\\n"


def test_init_force_overwrites_template_files_and_leaves_others_alone(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "bot"
    folder.mkdir()
    for name in TEMPLATE_NAMES:
        (folder / name).write_text("old\\n", encoding="utf-8")
    (folder / "notes.txt").write_text("keep\\n", encoding="utf-8")

    assert main(["init", "bot", "--force"]) == 0

    assert_matches_template(folder)
    assert sorted(p.name for p in folder.iterdir()) == sorted([*TEMPLATE_NAMES, "notes.txt"])
    assert (folder / "notes.txt").read_text(encoding="utf-8") == "keep\\n"


@pytest.mark.parametrize("force", [False, True])
def test_init_dir_that_is_an_existing_file_exits_two(tmp_path, monkeypatch, capsys, force):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bot").write_text("a file\\n", encoding="utf-8")

    assert main(["init", "bot", * (["--force"] if force else [])]) == 2

    assert capsys.readouterr().err.startswith("error:")
    assert (tmp_path / "bot").read_text(encoding="utf-8") == "a file\\n"


# printed run command


def test_init_prints_run_command_with_dotted_module_relative_to_cwd(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["init", "agents/my_bot"])

    assert run_line(capsys.readouterr().out) == (
        "uv run aea run agents/my_bot/dataset.jsonl --agent agents.my_bot.agent:build_agent --epochs 3 --max-samples 4"
    )


def test_init_with_absolute_dir_inside_cwd_still_uses_dotted_relative_module(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "agents" / "my_bot"

    main(["init", str(target)])

    line = run_line(capsys.readouterr().out)
    assert f"uv run aea run {target.as_posix()}/dataset.jsonl " in line
    assert "--agent agents.my_bot.agent:build_agent --epochs 3 --max-samples 4" in line


def test_init_dir_outside_cwd_creates_folder_prints_note_and_placeholder(tmp_path, monkeypatch, capsys):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    target = tmp_path / "outside" / "bot"

    assert main(["init", str(target)]) == 0

    out = capsys.readouterr().out
    assert_matches_template(target)
    assert PLACEHOLDER in run_line(out)
    assert "note:" in out


@pytest.mark.parametrize("dir_arg", ["my-bot", "agents/2bot", "agents/class", "import/bot"])
def test_init_dir_with_non_module_segment_creates_folder_prints_note_and_placeholder(
    tmp_path, monkeypatch, capsys, dir_arg
):
    monkeypatch.chdir(tmp_path)

    assert main(["init", dir_arg]) == 0

    out = capsys.readouterr().out
    assert_matches_template(tmp_path / dir_arg)
    line = run_line(out)
    assert line == f"uv run aea run {dir_arg}/dataset.jsonl {PLACEHOLDER} --epochs 3 --max-samples 4"
    assert "note:" in out


def test_init_valid_module_dir_prints_no_note(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["init", "agents/my_bot"])

    out = capsys.readouterr().out
    assert "note:" not in out
    assert PLACEHOLDER not in out
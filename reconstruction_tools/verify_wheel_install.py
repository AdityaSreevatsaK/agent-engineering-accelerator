"""Offline release-package smoke test for reconstructed AEA.

The wheel is built separately. This test installs that wheel into a disposable
virtual environment (not the checkout) and exercises the installed aea
console script and packaged templates. No provider accounts, external model
calls, historical fixtures, or claims of original source fidelity.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REQUIRED_TEMPLATES = ("agent.py", "dataset.jsonl")
EXPECTED_VERSION = "2.2.0"


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command {args!r} returned {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def check_wheel_contents(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as zf:
        members = set(zf.namelist())
        for name in REQUIRED_TEMPLATES:
            target = f"agent_accelerator/template/{name}"
            if target not in members:
                raise AssertionError(f"Missing packaged template: {target}")
            expected = (ROOT / "src" / target).read_bytes()
            actual = zf.read(target)
            if actual != expected:
                raise AssertionError(f"Wheel template differs from checked-in {target}")
        if not any(
            member.endswith(".dist-info/entry_points.txt") for member in members
        ):
            raise AssertionError("Built wheel contains no console-script metadata")


def main() -> None:
    wheels = sorted(DIST.glob("*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"Expected exactly one wheel in {DIST}, got {wheels}")
    wheel = wheels[0]
    check_wheel_contents(wheel)

    with tempfile.TemporaryDirectory(prefix="aea-wheel-smoke-") as tmp:
        root = Path(tmp)
        install_dir = root / "venv"
        venv.EnvBuilder(with_pip=True).create(install_dir)
        if sys.platform == "win32":
            interpreter = install_dir / "Scripts" / "python.exe"
            cli = install_dir / "Scripts" / "aea.exe"
        else:
            interpreter = install_dir / "bin" / "python"
            cli = install_dir / "bin" / "aea"
        run(
            str(interpreter),
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--no-input",
            "install",
            str(wheel.resolve()),
        )

        metadata = (
            "from importlib.metadata import version, entry_points; "
            "from importlib.resources import files; "
            "from pathlib import Path; "
            "import agent_accelerator, sys; "
            f"assert version('agent-accelerator') == '{EXPECTED_VERSION}'; "
            "assert any(ep.name == 'aea' and ep.value == 'agent_accelerator.cli:main' "
            "for ep in entry_points(group='console_scripts')); "
            "assert Path(agent_accelerator.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); "
            "assert files('agent_accelerator').joinpath('template', 'agent.py').is_file(); "
            "assert files('agent_accelerator').joinpath('template', 'dataset.jsonl').is_file()"
        )
        run(str(interpreter), "-c", metadata, cwd=root)

        if not cli.is_file():
            raise AssertionError(f"Installed aea entry point is absent: {cli}")
        help_result = run(str(cli), "--help", cwd=root)
        for command in ("init", "run", "compare", "report", "check", "export"):
            if command not in help_result.stdout:
                raise AssertionError(f"Installed CLI --help missing {command!r}")

        starter = root / "ready_agent"
        run(str(cli), "init", str(starter), cwd=root)
        for name in REQUIRED_TEMPLATES:
            # _init intentionally emits LF on Windows; check semantic text fidelity.
            # Raw byte fidelity of wheel assets was validated above separately.
            actual = (starter / name).read_text(encoding="utf-8")
            expected = (ROOT / "src" / "agent_accelerator" / "template" / name).read_text(
                encoding="utf-8"
            )
            if actual != expected:
                raise AssertionError(f"aea init template differs from source text: {name}")

        # Overwrite behaviour must work via the installed script as well.
        (starter / "agent.py").write_text("# overwritten by force\n", encoding="utf-8")
        run(str(cli), "init", str(starter), "--force", cwd=root)
        expected_agent = (ROOT / "src" / "agent_accelerator" / "template" / "agent.py").read_text(
            encoding="utf-8"
        )
        if (starter / "agent.py").read_text(encoding="utf-8") != expected_agent:
            raise AssertionError("aea init --force did not restore the packaged template")

        report = root / "report.md"
        output = root / "report.html"
        report.write_text(
            "# Offline report\n\nA safe verification.\n\n"
            "<script>not_executable()</script>\n",
            encoding="utf-8",
        )
        run(str(cli), "export", str(report), "--format", "html", "--output", str(output), cwd=root)
        if not output.is_file():
            raise AssertionError("Installed CLI HTML export produced no file")
        html = output.read_text(encoding="utf-8")
        if "<script>not_executable()</script>" in html:
            raise AssertionError("HTML export did not escape untrusted Markdown HTML")
        if "&lt;script&gt;" not in html:
            raise AssertionError("HTML export did not preserve escaped content")

        print(
            f"PASSED: wheel {wheel.name}; fresh installed CLI, metadata, "
            "bundled templates, init/force, and HTML escaping."
        )
        print("Historical example/fixture fidelity and live cloud providers: NOT tested.")


if __name__ == "__main__":
    main()

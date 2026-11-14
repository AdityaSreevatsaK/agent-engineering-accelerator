"""Install a built wheel in a disposable environment and exercise its CLI entry point."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("agent.py", "dataset.jsonl")
COMMANDS = ("init", "doctor", "run", "check", "compare", "report", "export", "backups")


def run(*argv: str, cwd: Path, timeout: int = 240) -> str:
    p = subprocess.run(
        list(argv), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )
    if p.returncode:
        raise AssertionError(
            f"Command {argv} failed ({p.returncode})\nstdout:\n{p.stdout[-2800:]}\n"
            f"stderr:\n{p.stderr[-2800:]}"
        )
    return p.stdout


def verify_wheel(wheel: Path) -> None:
    with ZipFile(wheel) as zipped:
        items = set(zipped.namelist())
        for name in TEMPLATES:
            rel = f"agent_accelerator/template/{name}"
            if rel not in items:
                raise AssertionError(f"Wheel missing bundled template {rel}")
            source = ROOT / "src" / rel
            if zipped.read(rel) != source.read_bytes():
                raise AssertionError(f"Wheel template differs from source: {rel}")
        if not any(name.endswith(".dist-info/entry_points.txt") for name in items):
            raise AssertionError("Wheel missing CLI entry point metadata")


def main() -> None:
    wheels = list((ROOT / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"Expected exactly one built wheel; got {len(wheels)}")
    wheel = wheels[0]
    verify_wheel(wheel)
    with TemporaryDirectory(prefix="aea-wheel-test-") as folder:
        temp = Path(folder)
        env = temp / "venv"
        run("uv", "venv", "--python", sys.executable, str(env), cwd=temp)
        py = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run("uv", "pip", "install", "--python", str(py), str(wheel.resolve()), cwd=temp, timeout=360)

        metadata_code = (
            "from importlib.metadata import entry_points, version;"
            "from importlib.resources import files;"
            "import agent_accelerator, sys;"
            "from pathlib import Path;"
            "assert version('agent-accelerator') == '2.2.0';"
            "assert Path(agent_accelerator.__file__).resolve().is_relative_to(Path(sys.prefix).resolve());"
            "assert files('agent_accelerator').joinpath('template', 'agent.py').is_file();"
            "assert any(p.name == 'aea' for p in entry_points(group='console_scripts'))"
        )
        run(str(py), "-c", metadata_code, cwd=temp)
        aea = env / ("Scripts/aea.exe" if os.name == "nt" else "bin/aea")
        help_text = run(str(aea), "--help", cwd=temp)
        if any(item not in help_text for item in COMMANDS):
            raise AssertionError("Installed CLI help is missing documented commands")

        # Verify the shipped backup-inventory command is read-only, including
        # a folder that happens to contain an unrelated operator-owned file.
        candidate = temp / "approved-baseline"
        first = run(str(aea), "backups", str(candidate), cwd=temp)
        if "No retained AEA baseline backups found" not in first or candidate.exists():
            raise AssertionError("Installed CLI backup inventory changed a missing destination")
        prior = temp / ".approved-baseline.aea-backup-synthetic" / "previous"
        prior.mkdir(parents=True)
        marker = prior / "operator-notes.txt"
        marker.write_text("retain exactly", encoding="utf-8")
        found = run(str(aea), "backups", str(candidate), cwd=temp)
        if prior.as_posix() not in found or marker.read_text(encoding="utf-8") != "retain exactly":
            raise AssertionError("Installed CLI backup inventory failed to preserve retained data")

        starter = temp / "new_agent"
        run(str(aea), "init", str(starter), cwd=temp)
        for name in TEMPLATES:
            if (starter / name).read_bytes() != (ROOT / "src/agent_accelerator/template" / name).read_bytes():
                raise AssertionError(f"Installed CLI generated incorrect {name}")

        # Import-only preflight must work from an installed *base* wheel with no
        # Strands or LangGraph extra and without generating evaluation artefacts.
        application = temp / "doctor_agent.py"
        application.write_text(
            "def build_agent():\n"
            "    raise AssertionError('doctor must not call the factory')\n",
            encoding="utf-8",
        )
        cases = temp / "doctor_cases.jsonl"
        cases.write_text(
            '{"id":"synthetic-1","input":"synthetic input","expected_output":"synthetic output"}\n',
            encoding="utf-8",
        )
        preflight = run(
            str(aea), "doctor", str(cases), "--agent", "doctor_agent:build_agent",
            cwd=temp,
        )
        if "PASS: preflight complete" not in preflight or (temp / "runs").exists():
            raise AssertionError("Installed doctor failed import-only validation or created a run")

        page = temp / "input.md"
        page.write_text("# Report\n\n<script>alert(1)</script>\n", encoding="utf-8")
        html = temp / "output.html"
        run(str(aea), "export", str(page), "--format", "html", "--output", str(html), cwd=temp)
        output = html.read_text(encoding="utf-8")
        if "<script>" in output or "&lt;script&gt;" not in output:
            raise AssertionError("Installed CLI HTML exporter failed to escape source text")

        print("PASS: built wheel, isolated install, CLI help/init/backups, and HTML export escaping")


if __name__ == "__main__":
    main()

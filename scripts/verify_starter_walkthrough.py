"""Verify that the documented generated starter works end-to-end with no edits or credentials.

Calls the installed package public CLI from a new unrelated working directory.
Uses the bundled offline model, not the starter's Bedrock factory.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROVIDER_KEYS = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
)


def run_cli(cwd: Path, *args: str, markers: tuple[str, ...] = ()) -> str:
    env = {**os.environ, **{key: "" for key in PROVIDER_KEYS}}
    env.update({"PYTHONUTF8": "1", "AWS_EC2_METADATA_DISABLED": "true"})
    command = [sys.executable, "-m", "agent_accelerator.cli", *args]
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180, check=False,
    )
    if result.returncode != 0 or any(marker not in result.stdout for marker in markers):
        # This only processes bundled synthetic data, but keep error output bounded.
        raise AssertionError(
            f"starter command {args[0]!r} failed: exit={result.returncode}; "
            f"missing={tuple(x for x in markers if x not in result.stdout)}; "
            f"stderr_tail={result.stderr[-400:]}"
        )
    return result.stdout


def run_walkthrough() -> None:
    with TemporaryDirectory(prefix="aea-generated-starter-") as folder:
        cwd = Path(folder)
        base = cwd / "baseline"
        runs = cwd / "runs"
        agent = "starter_agent.agent:build_offline_agent"
        dataset = "starter_agent/dataset.jsonl"

        run_cli(cwd, "init", "starter_agent", markers=("Created starter_agent/agent.py",))
        if not (cwd / "starter_agent" / "agent.py").is_file():
            raise AssertionError("Starter source missing after init")

        run_cli(
            cwd, "doctor", dataset, "--adapter", "strands", "--agent", agent,
            markers=("OK dataset: 5 valid case(s)", "PASS: preflight complete"),
        )
        if runs.exists():
            raise AssertionError("Doctor created evaluation artefacts")

        run_cli(
            cwd, "check", dataset, "--adapter", "strands", "--agent", agent,
            "--baseline", str(base), "--runs-dir", str(runs / "freeze"),
            "--max-samples", "1", "--update-baseline",
            markers=("passed=5/5", "BASELINE frozen:"),
        )
        if len(list(base.glob("*.json"))) != 1 or not (base / "report.md").is_file():
            raise AssertionError("Starter baseline has no report/Inspect JSON")
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()}

        run_cli(
            cwd, "check", dataset, "--adapter", "strands", "--agent", agent,
            "--baseline", str(base), "--runs-dir", str(runs / "comparison"),
            "--max-samples", "1",
            markers=("passed=5/5", "OK: baseline"),
        )
        compared = list((runs / "comparison").rglob("comparison.md"))
        if len(compared) != 1 or "**OK**" not in compared[0].read_text(encoding="utf-8"):
            raise AssertionError("Starter produced no passing comparison")
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()}
        if before != after:
            raise AssertionError("Starter comparison modified frozen baseline")

        output = cwd / "starter-report.html"
        run_cli(cwd, "export", str(base / "report.md"), "--format", "html", "--output", str(output))
        if not output.is_file() or "<html" not in output.read_text(encoding="utf-8").lower():
            raise AssertionError("HTML report missing after starter export")

        run_cli(cwd, "backups", str(base), markers=("No retained AEA baseline backups found",))
        print("PASS: generated offline starter; doctor 5/5; frozen baseline; unchanged check; HTML export; backups")
        print("PASS: no provider credentials, app edits, or output files retained outside disposable directory")


if __name__ == "__main__":
    run_walkthrough()

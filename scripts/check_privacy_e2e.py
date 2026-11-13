"""Exercise redacted and opt-in capture through real offline Strands/LangGraph CLIs.

Only a synthetic sentinel is used. Temporary captured logs are deleted at the
end of the test and must not be committed or shared.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "AEA_PRIVATE_PAYLOAD_47d83bd9c1a24f60"
ADAPTERS = (
    ("strands", "examples.calculator.agent:build_agent"),
    ("langgraph", "examples.calculator.langgraph_agent:build_agent"),
)
SUFFIXES = {".json", ".jsonl", ".md", ".html"}


def run_case(dataset: Path, directory: Path, adapter: str, agent: str, capture: bool) -> list[Path]:
    argv = [
        sys.executable, "-m", "agent_accelerator.cli",
        "run", str(dataset),
        "--adapter", adapter, "--agent", agent,
        "--runs-dir", str(directory),
        "--max-samples", "1",
        *(["--capture-content"] if capture else []),
    ]
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "OPENAI_API_KEY": "",
        "AZURE_OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
    }
    proc = subprocess.run(
        argv, cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=240, check=False,
    )
    if proc.returncode != 0 or "status=success" not in proc.stdout:
        raise AssertionError(
            f"{adapter} capture={capture}: CLI returned {proc.returncode}\n"
            f"stdout: {proc.stdout[-1200:]}\nstderr: {proc.stderr[-1200:]}"
        )
    if not capture and SENTINEL in (proc.stdout + proc.stderr):
        raise AssertionError(f"{adapter} emitted synthetic private input to its CLI output")
    paths = [p for p in directory.rglob("*") if p.is_file() and p.suffix in SUFFIXES]
    if not any(p.suffix == ".json" for p in paths):
        raise AssertionError(f"{adapter}: missing Inspect JSON result")
    if not any(p.name == "traces.jsonl" for p in paths):
        raise AssertionError(f"{adapter}: missing OpenTelemetry trace export")
    if not any(p.name == "report.md" for p in paths):
        raise AssertionError(f"{adapter}: missing report")
    return paths


def main() -> None:
    with TemporaryDirectory(prefix="aea-privacy-contract-") as root:
        folder = Path(root)
        dataset = folder / "cases.jsonl"
        dataset.write_text(
            json.dumps({
                "id": "privacy-test-001",
                "input": f"What is 2 plus 3? Private note: {SENTINEL}",
                "expected_output": "5",
            }) + "\n",
            encoding="utf-8",
        )
        for adapter, agent in ADAPTERS:
            paths = run_case(dataset, folder / f"{adapter}-redacted", adapter, agent, False)
            for p in paths:
                if SENTINEL in p.read_text(encoding="utf-8", errors="replace"):
                    raise AssertionError(f"{adapter}: synthetic input leaked to {p.name}")
            print(f"PASS: {adapter} default logs, traces, report and CLI output redact the sentinel")

        captured = run_case(dataset, folder / "strands-captured", *ADAPTERS[0], True)
        logs = [p for p in captured if p.suffix == ".json"]
        if not any(SENTINEL in p.read_text(encoding="utf-8", errors="replace") for p in logs):
            raise AssertionError("Explicit capture did not preserve the synthetic test input")
        print("PASS: explicit capture contains the sentinel only in disposable opt-in outputs")
    print("PASS: captured test data removed with the temporary directory")


if __name__ == "__main__":
    main()

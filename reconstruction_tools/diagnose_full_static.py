"""Report full configured Ruff and basic Pyright diagnostics for reconstructed AEA.

This is a measurement, not a style/fidelity rewrite or a green static gate.
A nonzero tool exit caused by findings is recorded; tool crashes are fatal.
"""
from __future__ import annotations

import collections
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static-diagnostics"


def run_json(name: str, command: list[str], path: Path) -> dict:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=420,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"{name} crashed (exit {completed.returncode})\n"
            f"stdout: {completed.stdout[-2000:]}\n"
            f"stderr: {completed.stderr[-3000:]}"
        )
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{name} did not produce valid JSON (exit {completed.returncode}): "
            f"{completed.stdout[-1000:]} {completed.stderr[-1500:]}"
        ) from exc
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> None:
    OUT.mkdir(exist_ok=True)
    ruff = run_json(
        "Ruff",
        ["ruff", "check", "src/agent_accelerator", "--output-format", "json"],
        OUT / "ruff.json",
    )
    if not isinstance(ruff, list):
        raise TypeError("Expected Ruff list of finding objects")
    pyright = run_json(
        "Pyright",
        ["pyright", "--outputjson", "--pythonversion", "3.11", "src"],
        OUT / "pyright.json",
    )
    if not isinstance(pyright, dict) or "summary" not in pyright:
        raise TypeError("Expected Pyright JSON report with summary")

    ruff_codes = collections.Counter(item.get("code", "unknown") for item in ruff)
    pyright_items = pyright.get("generalDiagnostics", [])
    pyright_severity = collections.Counter(item.get("severity", "unknown") for item in pyright_items)
    pyright_rules = collections.Counter(item.get("rule", "unknown") for item in pyright_items)

    lines = [
        "# AEA historical reconstruction: full static diagnostics",
        "",
        "NON-GATING BASELINE. The configured Ruff E/F/I/UP/B and basic Pyright checks",
        "may include transcription problems, incompatible type stubs, and style findings.",
        "No diagnostics have been waived, corrected, or certified in this report.",
        "",
        f"- Ruff total findings: {len(ruff)}",
        f"- Pyright findings: {len(pyright_items)}",
        f"- Pyright summary: {json.dumps(pyright['summary'], sort_keys=True)}",
        "",
        "## Ruff code counts",
        "",
        *[f"- {code}: {count}" for code, count in ruff_codes.most_common()],
        "",
        "## Pyright severities",
        "",
        *[f"- {severity}: {count}" for severity, count in pyright_severity.most_common()],
        "",
        "## Pyright rule counts",
        "",
        *[f"- {rule}: {count}" for rule, count in pyright_rules.most_common()],
        "",
        "## Sample Ruff diagnostics (first 20)",
        "",
    ]
    for item in ruff[:20]:
        rel = str(item.get("filename", "")).replace(str(ROOT) + "/", "")
        loc = item.get("location") or {}
        lines.append(
            f"- {rel}:{loc.get('row', '?')} {item.get('code', '?')}: "
            f"{item.get('message', '')}"
        )
    lines.extend(["", "## Sample Pyright diagnostics (first 20)", ""])
    for item in pyright_items[:20]:
        location = item.get("range", {}).get("start", {})
        lines.append(
            f"- {item.get('file', '?')}:{location.get('line', 0) + 1} "
            f"{item.get('severity', '?')} {item.get('rule', '?')}: "
            f"{str(item.get('message', '')).replace(chr(10), ' ')[:240]}"
        )

    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(
        "\nWARNING: These diagnostics are a measurement only. "
        "They are NOT a passing full Ruff/Pyright quality gate.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"STATIC DIAGNOSTIC EXECUTION FAILED: {exc}", file=sys.stderr)
        raise

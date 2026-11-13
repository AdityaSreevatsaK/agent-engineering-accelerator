"""Produce an inspectable, synthetic AEA pass-to-regression demonstration.

Choose an unused output directory. AEA never overwrites an existing demo folder
or deletes a prior evaluation. The generated baseline and logs are redacted by
default, but metadata and case identifiers remain and should be reviewed before
sharing.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

from verify_regression_gate import BAD, GOOD, command, require_success

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(folder: Path) -> dict[str, str]:
    return {
        str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def run_demo(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing demo path: {output}")
    output.mkdir(parents=True, exist_ok=False)
    baseline = output / "baseline"

    frozen = command(GOOD, baseline, output / "runs" / "freeze", update=True)
    require_success("freeze", frozen, "passed=11/11", "BASELINE frozen:")
    before = fingerprint(baseline)
    if not before:
        raise AssertionError("Baseline is empty")

    matched = command(GOOD, baseline, output / "runs" / "passing", update=False)
    require_success("passing", matched, "passed=11/11", "OK: baseline")

    faulty = command(BAD, baseline, output / "runs" / "defective", update=False)
    matches = list((output / "runs" / "defective").rglob("comparison.md"))
    if faulty.returncode != 1 or "REGRESSION: baseline" not in faulty.stdout or len(matches) != 1:
        raise AssertionError(
            f"Faulty agent was not detected: exit={faulty.returncode}\n"
            f"stdout={faulty.stdout[-1600:]}\nstderr={faulty.stderr[-1200:]}"
        )
    failing_report = matches[0]
    report_text = failing_report.read_text(encoding="utf-8")
    if "## Newly failing" not in report_text or "refund" not in report_text.lower():
        raise AssertionError("Failed-case explanation missing from the comparison report")
    if fingerprint(baseline) != before:
        raise AssertionError("Approved baseline changed during comparison")

    rendered = output / "regression-report.html"
    export = subprocess.run(
        [
            sys.executable, "-m", "agent_accelerator.cli",
            "export", str(failing_report), "--format", "html", "--output", str(rendered),
        ],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False,
    )
    if export.returncode or not rendered.is_file():
        raise AssertionError(f"HTML export failed: {export.stderr[-1500:]}")

    relative = failing_report.relative_to(output).as_posix()
    content = f"""# AEA demonstration: controlled regression

This folder contains **locally generated synthetic data**, not customer data.

## Live results

| Stage | Actual result |
| --- | --- |
| Freeze baseline | PASS, 11/11 cases |
| Re-run approved agent | PASS, 11/11 cases; no regression |
| Re-run deliberately defective refund agent | REGRESSION detected; CLI exit code 1 |
| Preserve approved baseline | PASS, SHA-256 fingerprints unchanged |
| Render human-readable report | PASS, self-contained HTML created |

## Evidence

- [Regression comparison](<{relative}>)
- [HTML comparison report](<regression-report.html>)
- Baseline directory: approved evaluation data, unchanged after both checks
- Runs directory: passing and deliberately defective CLI evaluations

## Demonstration talking points

1. Existing agents can be wrapped with an adapter and evaluated against a JSONL dataset.
2. Evaluations record case pass/fail, tool behaviour, numerical quality metrics and traces.
3. AEA detects a deliberately introduced defect without modifying the approved baseline.
4. The same check can become an offline pull-request quality gate.
5. This verifies deterministic local behaviour only, **not** live model repeatability, client security approval or organisational adoption.

**Privacy:** Prompt and tool payloads are redacted by default, but case identifiers,
file paths and trace names may remain. Review all outputs before sharing.
"""
    (output / "DEMO.md").write_text(content, encoding="utf-8")
    print(f"PASS: synthetic AEA demonstration created at {output.resolve()}")
    print(f"PASS: regression detected, approved baseline unchanged, HTML report at {rendered}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="An unused directory for demo outputs")
    args = parser.parse_args()
    run_demo(args.output_dir)


if __name__ == "__main__":
    main()

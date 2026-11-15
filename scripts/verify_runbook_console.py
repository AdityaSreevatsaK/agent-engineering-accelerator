"""Verify literal user-facing 'uv run --locked aea' commands from integration directories.

The existing acceptance uses Python -m, whose import-path rules differ from a
generated console entrypoint. This check proves both published CLI experiences.
Never invokes paid models; uses only synthetic applications and temporary runs.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_independent_integrations import SCENARIOS, CREDENTIALS, comparison_path


def command(app: Path, *args: str, expected: int, markers: tuple[str, ...]) -> None:
    env = {**os.environ, **{key: "" for key in CREDENTIALS}}
    env.update({"AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"})
    result = subprocess.run(
        ["uv", "run", "--locked", "aea", *args],
        cwd=app, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=300,
    )
    if result.returncode != expected or any(marker not in result.stdout for marker in markers):
        raise AssertionError(
            f"{app.name}: published console command {args[0]} returned {result.returncode}, "
            f"expected {expected}; missing={[s for s in markers if s not in result.stdout]}; "
            f"stderr_tail={result.stderr[-480:]}"
        )


def main() -> None:
    with TemporaryDirectory(prefix="aea-documented-console-cli-") as folder:
        root = Path(folder)
        for name, _framework, app in SCENARIOS:
            baseline = root / name / "baseline"
            run_base = root / name / "runs"
            common = (
                "dataset.jsonl", "--config", "aea.toml",
                "--baseline", str(baseline), "--max-samples", "1",
            )
            command(app, "doctor", "dataset.jsonl", "--config", "aea.toml", expected=0,
                    markers=("OK dataset: 12 valid case(s)", "PASS: preflight complete"))
            command(app, "check", *common, "--runs-dir", str(run_base / "freeze"), "--update-baseline",
                    expected=0, markers=("passed=12/12", "BASELINE frozen:"))
            command(app, "check", *common, "--runs-dir", str(run_base / "clean"),
                    expected=0, markers=("passed=12/12", "OK: baseline"))
            command(app, "check", *common, "--agent", "agent:build_broken_agent",
                    "--runs-dir", str(run_base / "defect"),
                    expected=1, markers=("REGRESSION: baseline",))
            report = comparison_path(run_base / "defect").read_text(encoding="utf-8")
            if "## Newly failing" not in report:
                raise AssertionError(f"{name}: console CLI has no actionable regression report")
            print(f"PASS {name}: real console entrypoint from application directory; "
                  "doctor, freeze, unchanged and expected defect", flush=True)
    print("PASS: full documented CLI commands work in both independent application directories")


if __name__ == "__main__":
    main()

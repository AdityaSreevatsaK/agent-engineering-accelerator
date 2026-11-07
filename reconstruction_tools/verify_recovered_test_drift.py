"""Fail-closed provenance audit of reconstructed original test modules.

Compare 14 historical video-derived FULL_DRAFT sources with the corresponding
executable tests. Ten must match exactly. The other four must differ ONLY in
the concrete, previously identified implementation compatibility corrections.

Do not edit historical drafts to make an executable test pass: originals remain
immutable provisional evidence. This does NOT certify original video bytes.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "reconstruction_drafts"
TESTS = ROOT / "tests" / "unit"

EXACT = (
    "test_build_task",
    "test_export",
    "test_init",
    "test_judge_double",
    "test_judge_double_pairwise",
    "test_judge_interrupt",
    "test_report_pairwise",
    "test_run_task",
    "test_scrub",
    "test_stats_compare",
)

# Every tuple is (historical draft text, documented execution-compatible text,
# expected number of occurrences). This is a transparent diff contract, not
# permission to silently refactor recorded source.
CORRECTIONS = {
    "test_cli_pairwise": (
        (
            '        monkeypatch.setattr(run_module, "_adapter_solver", lambda adapter, agent, **maps: fixed_answers(answers))',
            '''        # Runtime test adaptation: preserve the original draft separately; match run.py positional contract.
        monkeypatch.setattr(
            run_module, "_adapter_solver",
            lambda adapter, agent, input_map=None, output_map=None: fixed_answers(answers),
        )''',
            1,
        ),
    ),
    "test_judge": (
        (
            'FENCE_LINE = re.compile(r"<<<(BEGIN|END)-([A-Z]+) ([^>]*)>>>")',
            'FENCE_LINE = re.compile(r"<<<(BEGIN|END) ([A-Z_]+) ([^>]*)>>>")',
            1,
        ),
        (
            'marker = re.search(r"<<<BEGIN NAME. ([0-9a-f]{16})>>>", system).group(1)',
            'marker = re.search(r"<<<BEGIN NAME ([0-9a-f]{16})>>>", system).group(1)',
            2,
        ),
        (
            'fixed_answers(answers or {}, 0, {})',
            'fixed_answers(answers or {}, (), {})',
            1,
        ),
    ),
    "test_readings": (
        (
            '("## Tool use", "tool use"),',
            '("## Tool use", "tool_use"),',
            1,
        ),
        (
            '@pytest.mark.parametrize("epochs", [(1, "1 epoch"), (2, "2 epochs")], ids=["one-epoch", "two-epochs"])',
            '@pytest.mark.parametrize(("epochs", "count"), [(1, "1 epoch"), (2, "2 epochs")], ids=["one-epoch", "two-epochs"])',
            1,
        ),
    ),
    "test_report": (
        (
            '    assert report.splitlines()[-1] == "| ok | pass | n/a | n/a | n/a |  |"',
            '    assert report.splitlines()[-1] == "| ok | pass | n/a | n/a | n/a | |"',
            1,
        ),
        (
            '''    assert [
        line for line in judge_section(report) if not line.startswith("-") and ("label" in line or "appa" in line)
    ] == []''',
            '''    # General judge guidance may mention human labels; only calibration metrics must be absent.
    assert not any(
        line.startswith(("- Human-labelled golden cases:", "- Agreement with human labels:", "- Cohen's kappa:"))
        for line in judge_section(report)
    )''',
            1,
        ),
    ),
}


def audit_one(name: str) -> None:
    path_a = DRAFTS / f"{name}_FULL_DRAFT.py"
    path_b = TESTS / f"{name}.py"
    historical = path_a.read_text(encoding="utf-8")
    actual = path_b.read_text(encoding="utf-8")
    ast.parse(historical, filename=str(path_a), feature_version=(3, 11))
    ast.parse(actual, filename=str(path_b), feature_version=(3, 11))

    expected = historical
    for before, after, occurrences in CORRECTIONS.get(name, ()):
        if expected.count(before) != occurrences:
            raise AssertionError(
                f"{name}: draft correction anchor changed; expected {occurrences} "
                f"occurrences, got {expected.count(before)}"
            )
        expected = expected.replace(before, after)
    if actual != expected:
        raise AssertionError(
            f"{name}: executable test source drifted beyond documented "
            "historical-draft compatibility changes"
        )
    print(
        f"PASS {name}: " +
        ("exact draft equality" if name in EXACT else "only documented deviations"),
        flush=True,
    )


def main() -> int:
    if set(EXACT) & set(CORRECTIONS):
        raise RuntimeError("Invalid provenance manifest: duplicate file classification")
    for name in (*EXACT, *CORRECTIONS):
        audit_one(name)
    print(
        f"PASS: {len(EXACT)} exact and {len(CORRECTIONS)} documented-correction "
        "draft-to-executable test sources. Original footage byte fidelity is NOT certified.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Prove the active pairwise judge tests differ from the video draft only as documented.

The 724-line original-video candidate remains unchanged. The executable copy
has one adapter-mock compatibility adjustment and one blank-line deletion; any
other drift is a hard failure. This is an internal provenance check, NOT proof
that the video transcription is byte-equal to the original machine.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "reconstruction_drafts" / "test_judge_pairwise_FULL_VIDEO_CANDIDATE.py"
ACTIVE = ROOT / "tests" / "unit" / "test_judge_pairwise_recovered_prefix.py"
VIDEO_DRAFT_SHA256 = "0549a438954a5666d8599f53e78f0ac8a8101095ebcb8a74bda9e8778583c6c7"

HISTORICAL_FIXTURE = (
    '            run_module, "_adapter_solver", lambda adapter, agent, **maps: '
    'fixed_answers(answers, tuple(agent_errors))'
)
RUNTIME_FIXTURE = (
    '            run_module, "_adapter_solver",\n'
    '            # Runtime-only fixture adaptation: run.py passes mapping args positionally.\n'
    '            lambda adapter, agent, input_map=None, output_map=None: '
    'fixed_answers(answers, tuple(agent_errors))'
)
HISTORICAL_SEPARATOR = (
    '        judge(JUDGE_DOUBLE, golden_path="golden.jsonl", baseline_path="missing-baseline")\n\n\n'
    'def test_agent_error_is_incorrect_and_not_judged_without_calling_the_judge('
)
ACTIVE_SEPARATOR = HISTORICAL_SEPARATOR.replace("\n\n\ndef", "\n\ndef")


def main() -> int:
    original_bytes = CANDIDATE.read_bytes()
    original = original_bytes.decode("utf-8")
    active = ACTIVE.read_text(encoding="utf-8")
    if hashlib.sha256(original_bytes).hexdigest() != VIDEO_DRAFT_SHA256:
        raise RuntimeError("Pairwise video candidate changed: investigate source evidence")
    if len(original.splitlines()) != 724:
        raise RuntimeError("Pairwise video candidate physical-line count changed")
    if original.count(HISTORICAL_FIXTURE) != 1:
        raise RuntimeError("Historical adapter mock site not unique")
    if original.count(HISTORICAL_SEPARATOR) != 1:
        raise RuntimeError("Historical blank-line site not unique")

    expected = original.replace(HISTORICAL_FIXTURE, RUNTIME_FIXTURE, 1)
    expected = expected.replace(HISTORICAL_SEPARATOR, ACTIVE_SEPARATOR, 1)
    if active != expected:
        raise RuntimeError(
            "Active pairwise tests drifted beyond the documented adapter fixture "
            "compatibility change and blank-line difference"
        )
    print(
        "PASS: full recovered pairwise test copy matches its video candidate "
        "except for the one reviewed adapter mock and a blank line."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

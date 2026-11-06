"""Verify a *provisional* redacted Inspect log reconstructed from screenshots.

User provided three overlapping full-screen views of an already-minified
calculator_broken_redacted JSON file. Exact historical byte identity cannot
be proved from images; preserve this copy outside tests/fixtures until reviewed.
This static validator requires neither Inspect AI nor any model credentials.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "reconstruction_drafts" / "calculator_broken_redacted_SCREENSHOT_CANDIDATE.json"
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"
ID_ORDER = (
    "add", "subtract", "multiply", "divide", "negative_operand",
    "decimal_operand", "divide_by_zero", "no_tool_for_chat", "json_output", "subtract_large",
)
SAMPLE_ORDER = (
    "add", "decimal_operand", "divide", "divide_by_zero", "json_output",
    "multiply", "negative_operand", "no_tool_for_chat", "subtract", "subtract_large",
)
FAILURES = {"subtract": "exact", "subtract_large": "subset"}


def validate() -> None:
    raw = CANDIDATE.read_text(encoding="utf-8")
    # A faithful screenshot-derived minified candidate, not a fabricated
    # source-byte-equivalence claim or a replacement for missing capture logs.
    if len(raw.splitlines()) != 1:
        raise AssertionError("broken screenshot candidate should be one minified JSON line")
    data = json.loads(raw)
    if data["version"] != 2 or data["status"] != "success":
        raise AssertionError("source screenshot log version/status changed")
    meta = data["metadata"]
    if meta["capture_content"] is not False or data["eval"]["metadata"] != meta:
        raise AssertionError("broken log must remain redacted and metadata unchanged")
    actual_hash = hashlib.sha256(DATASET.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if meta["dataset_sha256"] != actual_hash:
        raise AssertionError("redacted screenshot dataset hash does not match recovered dataset")
    if data["results"]["total_samples"] != 10 or data["results"]["completed_samples"] != 10:
        raise AssertionError("original screenshot lists ten completed samples")
    result_score = data["results"]["scores"][0]
    if result_score["metrics"]["accuracy"]["value"] != 0.8:
        raise AssertionError("original summary shows an accuracy of 0.8")
    samples = data["samples"]
    if tuple(s["id"] for s in samples) != SAMPLE_ORDER:
        raise AssertionError("screenshot sample order/overlap continuity mismatch")
    if len(samples) != 10 or len({s["id"] for s in samples}) != 10:
        raise AssertionError("screenshot must contain ten distinct samples")
    for sample in samples:
        case_id = sample["id"]
        if sample["input"] != "[REDACTED]" or sample["target"] != "[REDACTED]":
            raise AssertionError(f"unredacted input or target for {case_id}")
        if sample["output"]["completion"] != "" or sample["messages"] != []:
            raise AssertionError(f"unredacted conversation payload for {case_id}")
        if sample["metadata"]["model_id"] != "rule-based-double":
            raise AssertionError(f"recorded model provenance changed for {case_id}")
        score = sample["scores"]["case_checks"]
        failure = case_id in FAILURES
        if score["value"] != ("I" if failure else "C"):
            raise AssertionError(f"screenshot score mismatch for {case_id}")
        if score["metadata"]["checks"]["tool_calls"] is failure:
            raise AssertionError(f"screenshot tool-call check mismatch for {case_id}")
        if failure:
            if f"calculator({FAILURES[case_id]}) not found in order" not in score["explanation"]:
                raise AssertionError(f"failure explanation mismatch for {case_id}")
        elif score["explanation"] != "all checks passed":
            raise AssertionError(f"passing-case explanation mismatch for {case_id}")
    [reduction] = data["reductions"]
    reduction_samples = reduction["samples"]
    if reduction["scorer"] != "case_checks" or tuple(s["sample_id"] for s in reduction_samples) != ID_ORDER:
        raise AssertionError("reduction order/identity differs from screenshot")
    if len(reduction_samples) != 10 or sum(s["value"] for s in reduction_samples) != 8:
        raise AssertionError("expected eight passing and two failing reductions")
    print("Screenshot-backed redacted candidate valid: 10 samples, 8 pass, 2 fail; dataset SHA verified")
    print("This DOES NOT establish exact original byte-level fidelity or recover the capture-content log")


if __name__ == "__main__":
    validate()

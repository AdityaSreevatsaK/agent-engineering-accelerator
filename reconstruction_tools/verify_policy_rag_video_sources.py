"""Fidelity audit of original policy RAG source videos and screenshots.

Original Notepad++ recordings: policy_rag/rules.py, agent.py (7 November 2026).
Source edit measurements:
  rules.py: Windows CRLF, 215 displayed lines, 9,151 characters.
  agent.py: LF, 137 displayed lines, 6,147 characters.
Both reconstructed source texts match these editor dimensions exactly.
Screenshot JSONLs: 11 original dataset records and 6 golden references.
Matching dimensions and runtime results do not prove original-byte identity.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from agent_accelerator.dataset import load_dataset
from agent_accelerator.judge import load_golden

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "policy_rag"
CODE = {
    "rules.py": {
        "sha256": "f9f3deb3d3d4392fa00b2cbe3150df1fdfc35aa88ba1f344ac79caa26530bd9c",
        "chars": 8937, "lines": 215, "editor_chars": 9151, "eol": "CRLF",
    },
    "agent.py": {
        "sha256": "f2db2ca210ac1cc6ca036a9d18cb67e98c87b82359009f15469ce65b3e0351be",
        "chars": 6147, "lines": 137, "editor_chars": 6147, "eol": "LF",
    },
}
JSONL = {
    "dataset.jsonl": (
        "1ad6bfd990d8284c3556821a63962cea87c8a5faaf81e4d9d3b7666d8e425916",
        11,
    ),
    "golden.jsonl": (
        "84dd3e2452960110030ff7c176cf5d2a794615d047038f2b2d8fd6ea208c6813",
        6,
    ),
}
EXPECTED_IDS = (
    "hotel_cap_tier1_city", "hotel_cap_other_city", "booking_advance",
    "flight_class_long_haul", "meal_per_diem_international",
    "alcohol_not_reimbursable", "receipt_threshold", "submission_deadline",
    "mileage_rate", "taxi_query_rewritten", "out_of_corpus_pet_boarding",
)
GOLDEN_IDS = (
    "hotel_cap_tier1_city", "hotel_cap_other_city", "taxi_query_rewritten",
    "out_of_corpus_pet_boarding", "alcohol_not_reimbursable",
    "meal_per_diem_international",
)


def check() -> None:
    for filename, meta in CODE.items():
        text = (SOURCE / filename).read_text(encoding="utf-8")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != meta["sha256"]:
            raise AssertionError(f"{filename}: video-derived candidate changed")
        if len(text) != meta["chars"] or not text.endswith("\n"):
            raise AssertionError(f"{filename}: reconstructed LF text differs")
        if text.count("\n") + 1 != meta["lines"]:
            raise AssertionError(f"{filename}: video/editor displayed line mismatch")
        editor_chars = len(text) + (text.count("\n") if meta["eol"] == "CRLF" else 0)
        if editor_chars != meta["editor_chars"]:
            raise AssertionError(f"{filename}: original editor character count mismatch")
        ast.parse(text, filename=str(SOURCE / filename), feature_version=(3, 11))
        print(f"PASS {filename}: original video editor dimensions and AST match", flush=True)

    rows = {}
    for filename, (hash_value, expected_count) in JSONL.items():
        text = (SOURCE / filename).read_text(encoding="utf-8")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != hash_value:
            raise AssertionError(f"{filename}: screenshot-derived text drift")
        entries = [json.loads(line) for line in text.splitlines()]
        if len(entries) != expected_count or not text.endswith("\n"):
            raise AssertionError(f"{filename}: screenshot entry count/endings mismatch")
        if len({record["id"] for record in entries}) != expected_count:
            raise AssertionError(f"{filename}: duplicate case IDs")
        rows[filename] = entries

    if tuple(r["id"] for r in rows["dataset.jsonl"]) != EXPECTED_IDS:
        raise AssertionError("Source screenshot dataset ordering changed")
    if tuple(r["id"] for r in rows["golden.jsonl"]) != GOLDEN_IDS:
        raise AssertionError("Source screenshot golden ordering changed")
    if sum(r.get("label") == "pass" for r in rows["golden.jsonl"]) != 5:
        raise AssertionError("Five human pass labels expected in original screenshot")
    if "label" in rows["golden.jsonl"][-1] or "notes" in rows["golden.jsonl"][-1]:
        raise AssertionError("Original sixth golden entry has no human label/notes")
    for record in rows["dataset.jsonl"]:
        if "input" not in record:
            raise AssertionError("Missing policy Q&A input")
    cases = load_dataset(SOURCE / "dataset.jsonl")
    if tuple(c.id for c in cases) != EXPECTED_IDS:
        raise AssertionError("Real AEA case loader disagrees with screenshot")
    golden = load_golden(SOURCE / "golden.jsonl", {c.id for c in cases})
    if set(golden) != set(GOLDEN_IDS):
        raise AssertionError("Real AEA golden loader disagrees with screenshot")

    print("PASS: policy RAG eleven original dataset cases and six golden references")
    print("Screenshot/video candidate fidelity, NOT certified historical byte equality.")


if __name__ == "__main__":
    check()

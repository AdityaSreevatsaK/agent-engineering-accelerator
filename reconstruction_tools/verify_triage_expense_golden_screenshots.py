"""Validate screenshot-derived golden reference files without guessing source bytes.

Evidence: user-uploaded Notepad++ screenshots dated 7 November 2026 of
examples/triage/golden.jsonl and examples/expense/golden.jsonl.
Both full images display all records and the final blank editor line.

Git blob checksums pin this reconstruction candidate, not the historical
original bytes. The original agent outputs are tested independently by the
original test-video golden cases.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent_accelerator.dataset import load_dataset
from agent_accelerator.judge import load_golden

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "triage": {
        "blob": "af51553d7d356633fae34ad2215ab677818d1e36",
        "lf_chars": 2056,
        "editor_lines": 7,
        "ids": (
            "charged_twice_furious",
            "invoice_paid_status",
            "refund_status",
            "csv_export_known_issue",
            "password_reset",
            "dashboard_outage_high",
        ),
        "labelled": 5,
    },
    "expense": {
        "blob": "6e97141e6cdfc188fbdd6575e1c9d39c3a3608a6",
        "lf_chars": 2304,
        "editor_lines": 9,
        "ids": (
            "approve_clean",
            "receipt_missing_over_75",
            "receipt_missing_after_conversion",
            "reject_no_receipt",
            "per_diem_caps_meals",
            "refer_over_limit",
            "refer_over_limit_after_conversion",
            "refer_unsupported_currency",
        ),
        "labelled": 5,
    },
}


def validate_one(name: str) -> None:
    spec = FILES[name]
    directory = ROOT / "examples" / name
    path = directory / "golden.jsonl"
    source = path.read_text(encoding="utf-8")
    data = source.encode("utf-8")
    blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if blob != spec["blob"]:
        raise AssertionError(f"{name}: screenshot transcript changed; review original screenshot")
    if not source.endswith("\n") or len(source) != spec["lf_chars"]:
        raise AssertionError(f"{name}: screenshot transcript source length/endings drifted")
    if source.count("\n") + 1 != spec["editor_lines"]:
        raise AssertionError(f"{name}: original screenshot displayed line count drifted")
    rows = [json.loads(line) for line in source.splitlines()]
    ids = tuple(row["id"] for row in rows)
    if ids != spec["ids"]:
        raise AssertionError(f"{name}: screenshot entry ordering or IDs altered")
    if any(set(row) - {"id", "reference", "label", "notes"} for row in rows):
        raise AssertionError(f"{name}: unexpected golden fields")
    if sum(row.get("label") == "pass" for row in rows) != spec["labelled"]:
        raise AssertionError(f"{name}: screenshot label count mismatch")
    if any(("label" in row) != ("notes" in row) for row in rows):
        raise AssertionError(f"{name}: screenshot label/notes pair changed")
    for row in rows:
        if not isinstance(json.loads(row["reference"]), dict):
            raise AssertionError(f"{name}: reference must decode to a JSON object: {row['id']}")
    case_ids = {case.id for case in load_dataset(directory / "dataset.jsonl")}
    golden = load_golden(path, case_ids)
    if set(golden) != set(ids):
        raise AssertionError(f"{name}: original AEA golden loader differs from screenshot entries")
    print(
        f"PASS {name}: {len(ids)} golden references; {spec['labelled']} human labels; "
        f"{len(source)} LF chars; screenshot editor {spec['editor_lines']} lines; "
        "actual AEA dataset and golden models validate."
    )


def main() -> None:
    for name in FILES:
        validate_one(name)
    print("Both screenshot-derived source candidates validated; historical-byte identity NOT asserted.")


if __name__ == "__main__":
    main()

"""Audit original Orders sources from user-provided Notepad++ recording/screenshot.

Two complete 8 Nov 2026 videos: orders/rules.py has Unix LF 156 editor
lines, 6,581 characters; orders/agent.py Unix LF 109 editor lines,
3,871 characters. Both candidates precisely match these editor counts.

The user screenshot shows all 11 orders dataset records plus blank line 12.
No original source hashes were available; these pin reconstructed candidates,
NOT historical original-byte identity.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples" / "orders"
CODE = {
    "rules.py": ("57b5e11beb5f6612530a34605576b7c1b08064f6eb456c138424af2a29ae9400", 6581, 156),
    "agent.py": ("4e2240f361bb9d87b888f1f39634006ba15a4cbb0bdb9f2d7631ea7bcc726966", 3871, 109),
}
DATASET_SHA256 = "9e231d997349b061c81cecc6c8d7eb15c1cafab8e34bdcc77b6d6154f8e22c97"
EXPECTED_IDS = (
    "order_status", "order_not_found", "latest_order", "unknown_customer",
    "total_spend", "refund_eligible", "refund_not_delivered",
    "refund_outside_window", "refund_unknown_order",
    "order_summary_json", "out_of_scope",
)


def validate() -> None:
    for filename, (checksum, n_chars, lines) in CODE.items():
        path = BASE / filename
        source = path.read_text(encoding="utf-8")
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != checksum:
            raise AssertionError(f"{filename}: recorded-video candidate changed")
        if len(source) != n_chars or source.count("\n") + 1 != lines or not source.endswith("\n"):
            raise AssertionError(f"{filename}: original recorded editor dimensions changed")
        ast.parse(source, filename=str(path), feature_version=(3, 11))
        print(f"PASS {filename}: {lines} editor lines and {n_chars} LF characters, AST valid")

    source = (BASE / "dataset.jsonl").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != DATASET_SHA256:
        raise AssertionError("Orders dataset screenshot transcript changed")
    rows = [json.loads(line) for line in source.splitlines()]
    if len(rows) != 11 or source.count("\n") + 1 != 12:
        raise AssertionError("Screenshot originally had 11 records and blank line 12")
    if tuple(row["id"] for row in rows) != EXPECTED_IDS:
        raise AssertionError("Dataset screenshot IDs/order changed")
    if len({r["id"] for r in rows}) != 11:
        raise AssertionError("Duplicate dataset IDs")
    assert rows[9]["expected_json_schema"]["properties"]["item_count"]["const"] == 2
    assert [x["id"] for x in rows if x.get("forbidden_tools")] == [
        "refund_not_delivered", "refund_outside_window",
    ]
    print("PASS orders dataset: 11 screenshot cases; original source evidence pinned")
    print("Visible editor dimensions and functional validation are not lost-original-byte proof")


if __name__ == "__main__":
    validate()

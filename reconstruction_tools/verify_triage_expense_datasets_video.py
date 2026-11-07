"""Fidelity-labelled audit for two screenshot/video-derived AEA example datasets.

These original-path files were transcribed from the user's 7 November 2026
Notepad++ recordings. A matching editor length is corroborating evidence,
NOT original byte-level proof; both reconstructed line and character counts match the editor views.
No synthetic file is substituted for the original calculator Inspect fixtures.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent_accelerator.dataset import load_dataset
from examples.expense.rules import USD_RATES

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "triage": {
        "sha256": "50a6b7bb2bfd141d1fcbbd053c4277ddcd4bf8a75f21045c0ca6de2ba36ce4c4",
        "lf_characters": 6206,
        "editor_windows_characters": 6218,
        "ids": (
            "charged_twice_furious", "angry_invoice_dispute",
            "invoice_paid_status", "refund_status", "unknown_invoice",
            "payment_question_no_invoice_id", "csv_export_known_issue",
            "sso_login_loop", "dashboard_outage_high", "password_reset",
            "close_account", "other_low_priority",
        ),
    },
    "expense": {
        "sha256": "7298ffec709a55018e2f3ea7879cb65992bea5c5fcb90c3deb4ac9aa6599e97b",
        "lf_characters": 10962,
        "editor_windows_characters": 10974,
        "ids": (
            "approve_clean", "reject_alcohol_only",
            "receipt_missing_over_75", "receipt_boundary_and_small_conversion",
            "receipt_missing_after_conversion", "per_diem_caps_meals",
            "lodging_capped_standard_grade", "lodging_senior_grade_gbp",
            "refer_over_limit", "refer_over_limit_after_conversion",
            "reject_no_receipt", "refer_unsupported_currency",
        ),
    },
}


def verify_one(name: str, contract: dict) -> None:
    path = ROOT / "examples" / name / "dataset.jsonl"
    source = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest != contract["sha256"] or len(source) != contract["lf_characters"]:
        raise AssertionError(f"{name}: video-based source changed; reconcile with recording")
    if not source.endswith("\n") or source.count("\n") != 12:
        raise AssertionError(f"{name}: recorded 12-line JSONL structure or terminating LF changed")
    if not all(line and line.startswith('{"id": ') for line in source.splitlines()):
        raise AssertionError(f"{name}: original editor JSONL record formatting changed")
    cases = load_dataset(path)
    if tuple(case.id for case in cases) != contract["ids"]:
        raise AssertionError(f"{name}: recorded case ordering/IDs differ")
    for case in cases:
        schema = case.expected_json_schema
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise AssertionError(f"{name}: case {case.id} lacks recorded output JSON contract")
        if name == "triage":
            if schema.get("required") != ["category", "priority", "reply"]:
                raise AssertionError(f"{name}: case {case.id} triage output contract differs")
            if case.max_tool_calls is None:
                raise AssertionError(f"{name}: case {case.id} missing tool-budget assertion")
        else:
            claim = json.loads(case.input)
            if set(claim) != {"employee_grade", "trip", "lines"}:
                raise AssertionError(f"{name}: case {case.id} malformed recorded input claim")
            if not claim["lines"] or any(
                set(line) != {"category", "amount", "currency", "date", "receipt"}
                for line in claim["lines"]
            ):
                raise AssertionError(f"{name}: case {case.id} claim line fields differ")
            claimed = schema.get("properties", {}).get("claimed_usd", {}).get("const")
            rates = [USD_RATES.get(line["currency"]) for line in claim["lines"]]
            if claimed is not None and all(rate is not None for rate in rates):
                observed = round(sum(
                    round(float(line["amount"]) * float(rate), 2)
                    for line, rate in zip(claim["lines"], rates, strict=True)
                ), 2)
                if observed != claimed:
                    raise AssertionError(
                        f"{name}: case {case.id} claimed amount {claimed} != source-rule "
                        f"conversion {observed}"
                    )
    editor_chars_if_crlf = len(source) + source.count("\n")
    mismatch = editor_chars_if_crlf - contract["editor_windows_characters"]
    if mismatch != 0:
        raise AssertionError(
            f"{name}: screenshot editor character discrepancy changed ({mismatch})"
        )
    print(
        f"PASS {name}: 12 original-video JSONL cases, unique IDs, real Case schema, "
        f"editor line count=13, reconstructed CRLF length={editor_chars_if_crlf:,}, "
        f"recorded length={contract['editor_windows_characters']:,}, "
        f"difference={mismatch:+d}",
        flush=True,
    )


def main() -> None:
    for name, contract in EXPECTED.items():
        verify_one(name, contract)
    print(
        "Original video-byte fidelity NOT certified despite matched display "
        "counts. Neither dataset was replaced by a synthetic capture fixture.",
        flush=True,
    )


if __name__ == "__main__":
    main()

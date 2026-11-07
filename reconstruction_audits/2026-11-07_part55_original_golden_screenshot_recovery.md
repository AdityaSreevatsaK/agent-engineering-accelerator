# AEA original golden screenshot recovery (Part 55)

Date: 7 November 2026. Integration target: reconstruction/wip-checkpoint-2026-10-30.
Master remains untouched. The images were already provided in the user project; do not request duplicates.

## Image evidence

| Project Library screenshot | Exact recovered original path | Entries | Original displayed lines | Pass labels |
| --- | --- | ---: | ---: | ---: |
| image(20261107-080956).png | examples/triage/golden.jsonl | 6 | 7 | 5 |
| image(20261107-080834).png | examples/expense/golden.jsonl | 8 | 9 | 5 |

Both screenshots show every record from the first through last line, followed by a blank editor line.
JSONL records were manually transcribed preserving visible ID order, nested JSON reference strings, human pass labels and notes. Missing labels/notes on unlabelled records were not fabricated.

### Triage order
charged_twice_furious (pass), invoice_paid_status (pass), refund_status (pass), csv_export_known_issue (pass), password_reset (pass), dashboard_outage_high (unlabelled).

### Expense order
approve_clean (pass), receipt_missing_over_75 (pass), receipt_missing_after_conversion (pass), reject_no_receipt (pass), per_diem_caps_meals (pass), refer_over_limit (unlabelled), refer_over_limit_after_conversion (unlabelled), refer_unsupported_currency (unlabelled).

## Validation

- Source integrity script pins reconstructed Git blob hashes, JSONL record and line counts, human labels, source IDs, and validation using real original AEA dataset and golden model loaders.
- Video-draft golden replay stages the original test_triage.py and test_expense.py source candidates unchanged under tests/unit, then executes one triage and two expense golden assertions including exact reference versus reconstructed agent reply.
- Native Inspect AI and LangGraph via Windows/Linux x Python 3.11/3.12 CI. No cloud calls or paid LLMs.

## Release boundary

These files are screenshot-derived original-source candidates. The screenshots do not include original file hashes or original editor character counts, so exact original byte equality cannot be asserted. Passing tests validates reference compatibility, not byte identity.
Historical original-path coverage rises from 64/117 to 66/117 after PR merge. Original calculator JSON fixtures, baseline logs, and remaining incomplete source transcripts are separate gaps.

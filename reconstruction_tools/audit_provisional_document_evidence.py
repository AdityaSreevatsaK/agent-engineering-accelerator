"""Guard independently reviewed semantics in AEA's *provisional* historical docs.

This is not a source-authentication test. The video is a visual record only;
the stored Markdown remains a commentary-bearing draft, not original bytes.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ordered_headers(source: str, headers: tuple[str, ...]) -> None:
    positions = [source.find(header) for header in headers]
    if any(index < 0 for index in positions) or positions != sorted(positions):
        raise AssertionError(f"Document section order changed: {headers}")


def audit_acceptance(content: str) -> None:
    ordered_headers(
        content,
        (
            "## 1. Confirmed decisions",
            "## 2. Agreed scope",
            "## 2a. Additions since 2.0.0",
            "## 3. Assumptions and recommendations",
            "## 4. Open items from decisions.md",
            "## 5. Commands (CLI completeness)",
            "## 6. Test coverage (unit tests only",
            "## 7. Known not-met items",
            "## 8. Summary",
        ),
    )
    start = content.index("## 1. Confirmed decisions")
    end = content.index("## 2. Agreed scope")
    decisions = re.findall(r"^\| D(\d{1,2}) \|", content[start:end], flags=re.MULTILINE)
    if decisions != [str(i) for i in range(1, 23)]:
        raise AssertionError("The 22 historically recorded decision rows must be preserved in order")
    commands = re.findall(r"^\| \x60aea (init|run|compare|report|check|export)\x60", content, flags=re.MULTILINE)
    if commands != ["init", "run", "compare", "report", "check", "export"]:
        raise AssertionError("The recorded CLI table must retain all six rows in order")
    for evidence in ("--max-p-value", "Fisher", "not re-run", "tests/unit/test_judge_pairwise.py"):
        if evidence not in content:
            raise AssertionError(f"Acceptance video evidence missing: {evidence}")
    if "not byte-for-byte" not in content and "not the original byte-for-byte" not in content:
        raise AssertionError("Provisional acceptance draft must disclaim historical byte identity")


def audit_review(content: str) -> None:
    ordered_headers(
        content,
        (
            "## 1. Dependencies",
            "## 2. Data stored",
            "## 2a. Metric storage",
            "## 3. Redaction guarantees",
            "## 4. Retention",
            "## 5. Security notes",
            "## 6. Residual risks",
            "## 7. Known limits",
        ),
    )
    retention = content.split("## 4. Retention", 1)[1].split("## 5. Security notes", 1)[0]
    for token in (
        "log.json", "traces.jsonl", "report.md", "baselines/<name>.json",
        "comparison*.md", "Custom", "No (the original review says",
    ):
        if token not in retention:
            raise AssertionError(f"Recorded six-row retention evidence absent: {token}")
    for token in ("trusted code", "before redaction", "--input-map", "--output-map"):
        if token not in content:
            raise AssertionError(f"Security boundary evidence missing: {token}")
    if "not byte-for-byte" not in content:
        raise AssertionError("Provisional security draft must disclaim historical byte identity")


def main() -> None:
    drafts = ROOT / "reconstruction_drafts"
    audit_acceptance((drafts / "docs_acceptance_video_PROVISIONAL.md").read_text(encoding="utf-8"))
    audit_review((drafts / "docs_review_video_PROVISIONAL.md").read_text(encoding="utf-8"))
    print("PASS: source-video-backed provisional acceptance and review semantics; NO original-byte claim")


if __name__ == "__main__":
    main()

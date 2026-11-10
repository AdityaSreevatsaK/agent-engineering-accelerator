"""Regression tests for the *semantic*, not byte-level, AEA docs reconstruction."""
from __future__ import annotations

import unittest

from reconstruction_tools.audit_provisional_document_evidence import (
    ROOT, audit_acceptance, audit_review,
)


class ProvisionalDocumentEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        drafts = ROOT / "reconstruction_drafts"
        cls.acceptance = (drafts / "docs_acceptance_video_PROVISIONAL.md").read_text(encoding="utf-8")
        cls.review = (drafts / "docs_review_video_PROVISIONAL.md").read_text(encoding="utf-8")

    def test_both_video_reviewed_semantic_drafts_pass(self):
        audit_acceptance(self.acceptance)
        audit_review(self.review)

    def test_acceptance_fisher_gate_caveat_cannot_disappear(self):
        with self.assertRaisesRegex(AssertionError, "max-p-value"):
            audit_acceptance(self.acceptance.replace("--max-p-value", "--other-p-value"))

    def test_acceptance_decision_matrix_cannot_drop_a_row(self):
        with self.assertRaisesRegex(AssertionError, "22 historically"):
            audit_acceptance(self.acceptance.replace("| D14 |", "| D14-missing |", 1))

    def test_review_retention_must_precede_security(self):
        mutated = self.review.replace("## 4. Retention", "## 5. Retention", 1)
        with self.assertRaisesRegex(AssertionError, "section order"):
            audit_review(mutated)

    def test_review_captured_report_payload_caveat_is_preserved(self):
        changed = self.review.replace("No (the original review says", "Yes (erroneous draft says", 1)
        with self.assertRaisesRegex(AssertionError, "retention evidence absent"):
            audit_review(changed)


if __name__ == "__main__":
    unittest.main()

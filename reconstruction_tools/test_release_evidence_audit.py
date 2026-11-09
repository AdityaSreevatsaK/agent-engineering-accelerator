"""Offline release-audit regression tests; no providers, secrets, or baselines opened."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reconstruction_tools.audit_original_paths import ROOT, load_inventory
from reconstruction_tools.audit_release_evidence import inspect, main, render_markdown
from reconstruction_tools.preflight_historical_ci import ARCHIVE, ORIGINAL


class ReleaseEvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aea_release_audit_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = self.root / "reconstruction_manifest" / "original_paths.txt"
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes((ROOT / "reconstruction_manifest/original_paths.txt").read_bytes())
        archive = self.root / ARCHIVE
        archive.parent.mkdir(parents=True)
        archive.write_bytes((ROOT / ARCHIVE).read_bytes())
        readme = self.root / "README.md"
        readme.write_text("# agent-engineering-accelerator\n", encoding="utf-8")
        for draft in (
            "reconstruction_drafts/docs_acceptance_video_PROVISIONAL.md",
            "reconstruction_drafts/docs_review_video_PROVISIONAL.md",
        ):
            file = self.root / draft
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("Provisional only\n", encoding="utf-8")

    def test_untracked_files_cannot_masquerade_as_recovered_sources(self):
        report = inspect(self.root, tracked=set())
        self.assertEqual(report["historical_inventory"]["present"], 0)
        self.assertEqual(report["historical_inventory"]["missing"], 117)
        self.assertEqual(report["release"]["state"], "blocked")
        self.assertFalse(report["release"]["approved_for_master"])
        self.assertEqual(len(report["historical_ci"]["missing_or_unsafe_prerequisites"]), 17)

    def test_provisional_drafts_do_not_count_as_historical_documents(self):
        report = inspect(self.root, tracked={"README.md"})
        documents = report["documentation"]["historical_docs"]
        self.assertTrue(documents["docs/acceptance.md"]["provisional_draft_present"])
        self.assertFalse(documents["docs/acceptance.md"]["original_present"])
        self.assertTrue(documents["docs/review.md"]["provisional_draft_present"])
        self.assertFalse(documents["docs/review.md"]["original_present"])
        self.assertTrue(report["documentation"]["root_readme_is_stub"])

    def test_unreadable_tracked_files_are_reported_separately(self):
        report = inspect(self.root, tracked={"README.md", "examples/orders/rules.py"})
        self.assertEqual(report["historical_inventory"]["present"], 2)
        self.assertEqual(
            report["historical_inventory"]["tracked_but_missing_or_linked"],
            ["examples/orders/rules.py"],
        )

    def test_strict_mode_never_grants_approval_based_on_missing_files(self):
        with patch("reconstruction_tools.audit_release_evidence.tracked_files", return_value=set()):
            self.assertEqual(
                main(["--root", str(self.root), "--require-release-ready"]), 1
            )

    def test_placeholder_inventory_does_not_grant_historical_fidelity(self):
        # For this test only: 117 dummy files demonstrate that path presence
        # is not a historical authenticity or formal release acceptance test.
        paths = load_inventory(self.root / "reconstruction_manifest/original_paths.txt")
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("SYNTHETIC PLACEHOLDER: NOT ORIGINAL\n", encoding="utf-8")
        (self.root / "uv.lock").write_text(
            'version = 1\nrequires-python = ">=3.11"\n[[package]]\nname = "dummy"\n',
            encoding="utf-8",
        )
        (self.root / ORIGINAL).write_bytes((self.root / ARCHIVE).read_bytes())
        (self.root / "README.md").write_text(
            "Test-only user documentation, not the historical README.\n" * 12,
            encoding="utf-8",
        )
        report = inspect(self.root, tracked=set(paths))
        self.assertEqual(report["historical_inventory"]["present"], 117)
        self.assertEqual(report["historical_inventory"]["missing"], 0)
        self.assertEqual(report["historical_ci"]["missing_or_unsafe_prerequisites"], [])
        self.assertEqual(report["historical_ci"]["preflight_issues"], [])
        self.assertEqual(report["release"]["state"], "requires_manual_review")
        self.assertFalse(report["release"]["automatic_source_byte_fidelity_certified"])
        self.assertFalse(report["release"]["approved_for_master"])

    def test_corrupted_archived_workflow_is_a_blocker(self):
        (self.root / ARCHIVE).unlink()
        report = inspect(self.root, tracked=set())
        self.assertTrue(report["historical_ci"]["preflight_issues"])
        self.assertTrue(any("Historical CI preflight" in x for x in report["release"]["blockers"]))

    def test_report_lists_missing_paths_and_does_not_claim_fidelity(self):
        rendered = render_markdown(inspect(self.root, tracked=set()))
        self.assertIn("Original files present: 0/117", rendered)
        self.assertIn("baselines/calculator.json", rendered)
        self.assertIn("Automatic source-byte certification: no", rendered)
        self.assertIn("Approved for master: no", rendered)

    def test_live_reconstruction_checkpoint_is_not_signed_off(self):
        # Uses Git-index paths, rather than relying on the source files listed
        # in these tests as evidence of their own historical authenticity.
        report = inspect(ROOT)
        inv = report["historical_inventory"]
        self.assertEqual(inv["expected"], 117)
        self.assertGreaterEqual(inv["present"], 97)
        self.assertEqual(inv["present"] + inv["missing"], 117)
        self.assertFalse(report["release"]["approved_for_master"])
        self.assertEqual(report["release"]["state"], "blocked")


if __name__ == "__main__":
    unittest.main()

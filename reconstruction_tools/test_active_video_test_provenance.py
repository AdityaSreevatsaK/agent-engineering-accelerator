"""Negative tests for reconstructed-test provenance and transcript fragment checks."""
from __future__ import annotations

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from reconstruction_tools.verify_active_video_test_provenance import (
    CANDIDATES, DIRECT_COPIES, ROOT, assemble_langgraph_fragments,
    audit_all, editor_chars, git_blob_digest, inspect_active,
)


class VideoTestProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(prefix="aea-video-provenance-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        active_dir = self.root / "tests" / "unit"
        archived_dir = self.root / "reconstruction_drafts"
        active_dir.mkdir(parents=True)
        archived_dir.mkdir(parents=True)
        for name in CANDIDATES:
            original = ROOT / "tests" / "unit" / f"{name}.py"
            shutil.copyfile(original, active_dir / original.name)
        for filename in DIRECT_COPIES.values():
            shutil.copyfile(ROOT / "reconstruction_drafts" / filename, archived_dir / filename)
        for original in (ROOT / "reconstruction_drafts").glob("test_langgraph_adapter_PARTIAL_lines_*"):
            shutil.copyfile(original, archived_dir / original.name)

    def test_current_checkpoint_matches_reviewed_source(self):
        report = audit_all(root=self.root)
        self.assertEqual(len(report), 5)
        self.assertEqual(report["test_langgraph_adapter"]["lines_delta"], 0)
        self.assertEqual(report["test_langgraph_adapter"]["chars_delta"], -25)
        self.assertEqual(report["test_triage"]["lines_delta"], -5)
        self.assertEqual(report["test_triage"]["chars_delta"], -447)
        self.assertEqual(report["test_expense"]["lines_delta"], -2)
        self.assertEqual(report["test_expense"]["chars_delta"], -84)
        self.assertEqual(report["test_helpdesk"]["test_functions"], 19)
        self.assertEqual(report["test_policy_rag"]["test_functions"], 25)

    def test_unreviewed_change_in_active_candidate_rejected(self):
        name = "test_policy_rag"
        path = self.root / "tests" / "unit" / f"{name}.py"
        path.write_text(path.read_text(encoding="utf-8") + "# invented addition\n", encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "source candidate drifted"):
            inspect_active(name, root=self.root)

    def test_archived_copy_must_equal_triage_and_expense(self):
        for name, filename in DIRECT_COPIES.items():
            with self.subTest(name=name):
                path = self.root / "reconstruction_drafts" / filename
                original = path.read_text(encoding="utf-8")
                path.write_text(original + "# archive changed\n", encoding="utf-8")
                with self.assertRaisesRegex(AssertionError, "active test changed"):
                    audit_all(root=self.root)
                path.write_text(original, encoding="utf-8")

    def test_langgraph_recorded_fragments_are_complete_and_ordered(self):
        text = assemble_langgraph_fragments(root=self.root)
        self.assertEqual(text.count("\n"), 1006)
        fragment = self.root / "reconstruction_drafts" / "test_langgraph_adapter_PARTIAL_lines_951_1006.txt"
        fragment.unlink()
        with self.assertRaisesRegex(AssertionError, "expected 12 staged"):
            assemble_langgraph_fragments(root=self.root)

    def test_langgraph_fragment_change_detected(self):
        fragment = self.root / "reconstruction_drafts" / "test_langgraph_adapter_PARTIAL_lines_36_112.txt"
        text = fragment.read_text(encoding="utf-8")
        fragment.write_text(text.replace("SHARED_SAVER", "SHARED_SAVXR", 1), encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "differs from preserved"):
            assemble_langgraph_fragments(root=self.root)

    def test_invalid_recorded_line_ending_rejected(self):
        with self.assertRaises(ValueError):
            editor_chars("sample\n", "custom")

    def test_digest_depends_on_source_bytes_not_filesystem_location(self):
        self.assertEqual(git_blob_digest("sample\n"), git_blob_digest("sample\n"))
        self.assertNotEqual(git_blob_digest("sample\n"), git_blob_digest("sample \n"))


if __name__ == "__main__":
    unittest.main()

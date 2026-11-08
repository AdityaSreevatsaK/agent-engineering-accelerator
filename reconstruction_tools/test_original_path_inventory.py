"""Standard-library checks for the historical AEA path audit."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from reconstruction_tools.audit_original_paths import (
    EXPECTED, classify, load_inventory, summarise, tracked_files,
)


class OriginalPathInventoryTests(unittest.TestCase):
    def test_canonical_inventory_has_117_unique_paths_and_original_categories(self):
        paths = load_inventory()
        self.assertEqual(len(paths), 117)
        self.assertEqual(len(set(paths)), 117)
        for category, expected in EXPECTED.items():
            self.assertEqual(sum(classify(p) == category for p in paths), expected)

    def test_only_historical_paths_count(self):
        paths = ("tests/unit/test_a.py", "examples/triage/dataset.jsonl")
        tracked = {"tests/unit/test_a.py", "reconstruction_drafts/test_a.py",
                   "reconstruction_audits/some_checkpoint.md"}
        report = summarise(paths, tracked)
        self.assertEqual(report["present_original_paths"], 1)
        self.assertEqual(report["missing_original_paths"], 1)
        self.assertEqual(report["missing"], ["examples/triage/dataset.jsonl"])
        self.assertIn("fidelity", report["warning"])

    def test_duplicates_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "paths.txt"
            path.write_text("tests/unit/one.py\ntests/unit/one.py\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_inventory(path)

    def test_repository_checkout_meets_checkpoint_floor(self):
        report = summarise(load_inventory(), tracked_files())
        self.assertGreaterEqual(report["present_original_paths"], 85)
        self.assertEqual(
            report["present_original_paths"] + report["missing_original_paths"], 117
        )


if __name__ == "__main__":
    unittest.main()

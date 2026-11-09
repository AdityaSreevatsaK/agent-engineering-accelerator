"""Standard-library-only tests of historical CI activation preflight."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from reconstruction_tools.preflight_historical_ci import (
    ARCHIVE, ORIGINAL, ROOT, inspect, is_safe_file, main,
)
from reconstruction_tools.audit_original_paths import load_inventory


class HistoricalCiPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = self.root / "reconstruction_manifest/original_paths.txt"
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes((ROOT / "reconstruction_manifest/original_paths.txt").read_bytes())
        archive = self.root / ARCHIVE
        archive.parent.mkdir(parents=True)
        archive.write_bytes((ROOT / ARCHIVE).read_bytes())

    def activate(self, content: str | None = None):
        file = self.root / ORIGINAL
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            (self.root / ARCHIVE).read_text(encoding="utf-8") if content is None else content,
            encoding="utf-8",
        )

    def supply_prerequisites(self):
        paths = load_inventory(self.root / "reconstruction_manifest/original_paths.txt")
        for name in paths:
            if name.startswith("baselines/"):
                dest = self.root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text("placeholder for presence-only test", encoding="utf-8")
        for name in (
            "tests/fixtures/calculator_capture_content.json",
            "tests/fixtures/calculator_broken_redacted.json",
        ):
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("{}", encoding="utf-8")
        (self.root / "uv.lock").write_text(
            'version = 1\nrequires-python = ">=3.11"\n[[package]]\nname = "dummy"\n',
            encoding="utf-8",
        )

    def test_original_ci_stays_inactive_during_incomplete_recovery(self):
        self.assertFalse(inspect(self.root)["active"])
        self.assertEqual(len(inspect(self.root)["missing"]), 17)
        self.assertEqual(main(["--root", str(self.root)]), 0)

    def test_preflight_blocks_premature_activation(self):
        self.activate()
        self.assertTrue(inspect(self.root)["active"])
        self.assertEqual(main(["--root", str(self.root)]), 1)

    def test_presence_and_archived_workflow_match_are_necessary_only(self):
        self.supply_prerequisites()
        self.activate()
        self.assertEqual(inspect(self.root)["missing"], [])
        self.assertEqual(inspect(self.root)["issues"], [])
        self.assertEqual(main(["--root", str(self.root)]), 0)

    def test_changed_historical_workflow_is_rejected(self):
        self.supply_prerequisites()
        self.activate("name: unrelated\n")
        self.assertIn("differs", inspect(self.root)["issues"][0])
        self.assertEqual(main(["--root", str(self.root)]), 1)

    def test_malformed_lock_is_rejected(self):
        self.supply_prerequisites()
        self.activate()
        (self.root / "uv.lock").write_text("not valid TOML", encoding="utf-8")
        self.assertTrue(inspect(self.root)["issues"])
        self.assertEqual(main(["--root", str(self.root)]), 1)

    def test_archive_removal_is_rejected_even_if_workflow_inactive(self):
        (self.root / ARCHIVE).unlink()
        self.assertEqual(main(["--root", str(self.root)]), 1)

    def test_symlinked_prerequisite_is_not_accepted(self):
        self.supply_prerequisites()
        self.activate()
        target = self.root / "baselines/calculator.json"
        target.unlink()
        other = self.root / "outside.json"
        other.write_text("{}", encoding="utf-8")
        try:
            target.symlink_to(other)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"Symlink unavailable: {exc}")
        self.assertFalse(is_safe_file(self.root, "baselines/calculator.json"))
        self.assertIn("baselines/calculator.json", inspect(self.root)["missing"])
        self.assertEqual(main(["--root", str(self.root)]), 1)


if __name__ == "__main__":
    unittest.main()

"""Pure-stdlib guard for reconstructed operator README and missing-lock boundary.

The historical README was a title-only stub. The new guide must never be
mistaken for byte-authenticated original AEA documentation or a production
release signoff.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from reconstruction_tools.audit_release_evidence import inspect

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "reconstruction-modern-lock-ci.yml"


class ReconstructedReadmeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = README.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_readme_is_useful_but_explicitly_nonhistorical(self) -> None:
        self.assertTrue(self.text.startswith("# Agent Engineering Accelerator (AEA)"))
        for phrase in (
            "not production approved",
            "not",
            "historical original README",
            "not",
            "lost historical",
            "not",
            "97 of 117",
        ):
            self.assertIn(phrase.lower(), self.text.lower())
        self.assertGreater(len(self.text.splitlines()), 60)

    def test_readme_documents_offline_windows_and_no_paid_api(self) -> None:
        for phrase in (
            "WSL is **not** required",
            "uv lock",
            "uv sync --python 3.11 --all-extras --group dev --locked",
            "uv run --locked aea run examples/calculator/dataset.jsonl",
            "uv run --locked aea run examples/triage/dataset.jsonl",
            "uv run --locked aea check",
            "capture-content",
            "AEA is **not** a sandbox",
        ):
            self.assertIn(phrase.lower(), self.text.lower())

    def test_modern_lock_is_generated_not_committed_as_original(self) -> None:
        self.assertIn("uv lock", self.workflow)
        self.assertIn("uv sync --all-extras --group dev --locked", self.workflow)
        self.assertIn("upload-artifact@v4", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertIn("Original historical", self.workflow)
        self.assertNotIn("git push", self.workflow)
        self.assertNotIn("git add uv.lock", self.workflow)

    def test_release_audit_does_not_confuse_reconstructed_docs_with_signoff(self) -> None:
        evidence = inspect(ROOT)
        self.assertFalse(evidence["documentation"]["root_readme_is_stub"])
        self.assertFalse(evidence["release"]["automatic_source_byte_fidelity_certified"])
        self.assertFalse(evidence["release"]["approved_for_master"])
        self.assertEqual(evidence["release"]["state"], "blocked")


if __name__ == "__main__":
    unittest.main()

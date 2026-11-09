"""Negative tests proving acceptance source audit does not rely on prose claims."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from reconstruction_tools.audit_acceptance_source_contract import (
    ROOT, COMMANDS, CONFIG_FIELDS, REQUIRED_RUN_METADATA, assess, main,
)


class ReconstructedAcceptanceSourceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="aea_acceptance_source_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "src" / "agent_accelerator"
        source.mkdir(parents=True)
        for name in ("run.py", "cli.py", "config.py", "dataset.py"):
            shutil.copyfile(ROOT / "src" / "agent_accelerator" / name, source / name)

    def edit(self, filename: str, old: str, new: str) -> None:
        path = self.root / "src" / "agent_accelerator" / filename
        before = path.read_text(encoding="utf-8")
        self.assertEqual(before.count(old), 1, msg=f"Ambiguous source anchor in {filename}")
        path.write_text(before.replace(old, new), encoding="utf-8")

    def test_current_source_supports_core_but_not_full_provenance(self):
        report = assess(self.root)
        self.assertTrue(report["checks_pass"], report["issues"])
        self.assertEqual(set(report["CLI"]["commands"]), COMMANDS)
        self.assertEqual(set(report["configuration"]["toml_keys"]), CONFIG_FIELDS)
        provenance = report["provenance"]
        self.assertGreaterEqual(
            set(provenance["run_metadata_keys"]),
            REQUIRED_RUN_METADATA,
        )
        self.assertIn("dataset_sha256", provenance["task_metadata_keys"])
        self.assertIn("config", provenance["task_metadata_keys"])
        self.assertTrue(provenance["dataset_sha256_normalises_crlf"])
        self.assertFalse(provenance["config_content_hash_found"])
        self.assertFalse(provenance["git_revision_found"])
        self.assertFalse(provenance["dependency_versions_found"])
        self.assertEqual(
            report["historical_acceptance_reassessment"]["D11_reproducible_provenance"],
            "partly verified",
        )
        self.assertIn("config_content_hash_found", provenance)
        self.assertNotIn("--max-cost", report["CLI"]["flags"])
        self.assertNotIn("--max-latency", report["CLI"]["flags"])

    def test_removing_dataset_digest_breaks_task_contract(self):
        self.edit("run.py", '"dataset_sha256": dataset_sha256(dataset_path)', '"dataset_fingerprint": dataset_sha256(dataset_path)')
        report = assess(self.root)
        self.assertFalse(report["checks_pass"])
        self.assertTrue(any("Task metadata" in issue for issue in report["issues"]))

    def test_removed_version_field_breaks_runtime_contract(self):
        self.edit("run.py", '"accelerator_version": version("agent-accelerator")', '"package_build": version("agent-accelerator")')
        report = assess(self.root)
        self.assertFalse(report["checks_pass"])
        self.assertTrue(any("run metadata" in issue for issue in report["issues"]))

    def test_config_setting_drift_is_exposed(self):
        self.edit(
            "config.py",
            'CONFIG_KEYS = ("adapter", "agent", "input_map", "output_map")',
            'CONFIG_KEYS = ("adapter", "agent", "input_map")',
        )
        report = assess(self.root)
        self.assertFalse(report["checks_pass"])
        self.assertTrue(any("TOML config keys" in issue for issue in report["issues"]))

    def test_loss_of_explicit_capture_flag_is_exposed(self):
        self.edit("cli.py", '"--capture-content"', '"--capture-hidden"')
        report = assess(self.root)
        self.assertFalse(report["checks_pass"])
        self.assertFalse(report["privacy"]["capture_flag"])
        self.assertTrue(any("CLI capabilities" in issue for issue in report["issues"]))

    def test_loss_of_crlf_normalisation_is_exposed(self):
        self.edit("dataset.py", 'replace(b"\\r\\n", b"\\n")', 'replace(b"\\n", b"\\n")')
        report = assess(self.root)
        self.assertFalse(report["checks_pass"])
        self.assertFalse(report["provenance"]["dataset_sha256_normalises_crlf"])
        self.assertTrue(any("D20" in issue for issue in report["issues"]))

    def test_new_config_hash_triggers_manual_reassessment_not_fake_verification(self):
        self.edit(
            "run.py",
            '"dataset_path": dataset_path.as_posix(),',
            '"dataset_path": dataset_path.as_posix(),\n            "config_sha256": "NOT_AUTHENTICATED",',
        )
        report = assess(self.root)
        self.assertTrue(report["checks_pass"])
        self.assertTrue(report["provenance"]["config_content_hash_found"])
        self.assertEqual(
            report["historical_acceptance_reassessment"]["D11_reproducible_provenance"],
            "re-review required",
        )
        self.assertNotIn("source_byte_fidelity_certified", report)

    def test_json_cli_is_machine_readable_and_does_not_sign_off_release(self):
        # Running the CLI from a real checkout is deliberately read-only.
        self.assertEqual(main(["--root", str(ROOT), "--format", "json"]), 0)

    def test_missing_source_fails_explicitly(self):
        (self.root / "src" / "agent_accelerator" / "run.py").unlink()
        with self.assertRaises(FileNotFoundError):
            assess(self.root)


if __name__ == "__main__":
    unittest.main()

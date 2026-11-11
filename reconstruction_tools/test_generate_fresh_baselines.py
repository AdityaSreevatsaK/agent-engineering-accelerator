"""Safety and provenance checks for new synthetic-agent baseline generation."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from reconstruction_tools.generate_fresh_baselines import (
    BASELINES, Baseline, command, manifest_entry, preflight, run,
)


class FreshBaselineGenerationTests(unittest.TestCase):
    def test_baseline_catalogue_covers_the_seven_supported_offline_runs(self):
        self.assertEqual(
            [item.name for item in BASELINES],
            [
                "calculator-strands", "calculator-langgraph", "orders",
                "expense", "triage", "policy_rag", "helpdesk",
            ],
        )
        self.assertEqual(len({spec.name for spec in BASELINES}), len(BASELINES))

    def test_original_baselines_and_capture_options_are_never_referenced_as_targets(self):
        for spec in BASELINES:
            command_line = command(spec, Path("/tmp/baselines-new") / spec.name, Path("/tmp/runs"))
            self.assertIn("--update-baseline", command_line)
            self.assertIn("--max-samples", command_line)
            self.assertNotIn("--capture-content", command_line)
            self.assertNotIn("--judge", command_line)
            self.assertNotIn("baselines/", " ".join(command_line))
            self.assertIn("--agent", command_line)

    def test_preflight_refuses_existing_baseline_and_manifest(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("README.md").write_text("New baselines only\n", encoding="utf-8")
            spec = BASELINES[0]
            preflight((spec,), root)
            root.joinpath(spec.name).mkdir()
            with self.assertRaises(FileExistsError):
                preflight((spec,), root)
            root.joinpath(spec.name).rmdir()
            root.joinpath("manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                preflight((spec,), root)

    def test_preflight_refuses_missing_safety_readme(self):
        with TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                preflight((BASELINES[0],), Path(temp))

    def test_manifest_records_dataset_and_inspect_log_sha_without_prompt_text(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "examples" / "calculator" / "dataset.jsonl"
            dataset.parent.mkdir(parents=True)
            dataset.write_text('{"id":"one"}\n{"id":"two"}\n', encoding="utf-8")
            generated = root / "baselines-new" / "calculator-strands"
            generated.mkdir(parents=True)
            (generated / "log.json").write_text('{"status":"success"}', encoding="utf-8")
            (generated / "report.md").write_text("# Report", encoding="utf-8")
            spec = Baseline("calculator-strands", "examples/calculator/dataset.jsonl",
                            "strands", "examples.calculator.agent:build_agent")
            result = manifest_entry(spec, generated, root)
            self.assertEqual(result["case_count"], 2)
            self.assertEqual(result["dataset_sha256"], sha256(dataset.read_bytes()).hexdigest())
            self.assertEqual(result["inspect_log_sha256"], sha256((generated / "log.json").read_bytes()).hexdigest())
            self.assertFalse(result["capture_content"])
            self.assertNotIn("one", str(result))

    def test_dry_run_checks_files_without_generating_any_outputs(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "baselines-new"
            output.mkdir()
            (output / "README.md").write_text("New baseline directory", encoding="utf-8")
            dataset = root / BASELINES[0].dataset
            dataset.parent.mkdir(parents=True)
            dataset.write_text('{"id":"one"}\n', encoding="utf-8")
            self.assertEqual(run((BASELINES[0],), root=root, dry_run=True), 0)
            self.assertEqual([item.name for item in output.iterdir()], ["README.md"])


if __name__ == "__main__":
    unittest.main()

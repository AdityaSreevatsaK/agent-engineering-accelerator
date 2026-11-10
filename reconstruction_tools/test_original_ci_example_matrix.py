"""Manifest and safety unit tests for the seven-lane historical CI substitute.

No real agent, provider or historical baseline is executed by these tests;
the separate CI job exercises the actual native run/compare transitions.
"""
from __future__ import annotations

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from reconstruction_tools.replay_original_ci_example_matrix import (
    BY_LABEL, LANES, ROOT, digests, historical_invocations,
    verify_script_contract,
)


class OriginalCIExampleManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="aea-original-ci-script-manifest-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts" / "ci.sh", self.root / "scripts" / "ci.sh")
        for lane in LANES:
            target = self.root / lane.dataset
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()

    def test_original_script_covers_seven_examples(self):
        self.assertEqual(len(LANES), 7)
        self.assertEqual(len(BY_LABEL), len(LANES))
        self.assertEqual(set(historical_invocations()), set(BY_LABEL))
        verify_script_contract()
        verify_script_contract(self.root)

    def test_original_baseline_paths_are_labels_not_generated_files(self):
        self.assertEqual(
            {lane.historical_baseline for lane in LANES},
            {
                "baselines/calculator.json", "baselines/orders.json",
                "baselines/expense", "baselines/triage",
                "baselines/policy_rag", "baselines/helpdesk",
            },
        )
        self.assertEqual(sum(lane.cases for lane in LANES), 76)

    def test_original_orders_disagreement_is_not_silently_suppressed(self):
        orders = BY_LABEL["orders-strands"]
        self.assertEqual(orders.known_original_failures, frozenset({"total_spend"}))
        self.assertEqual(
            orders.new_mutant_failures,
            frozenset({"refund_not_delivered", "refund_outside_window"}),
        )
        self.assertTrue(all(not lane.known_original_failures for lane in LANES if lane != orders))

    def test_seven_mutants_have_nonempty_disjoint_failure_sets(self):
        self.assertTrue(all(lane.new_mutant_failures for lane in LANES))
        self.assertTrue(all(
            not (lane.known_original_failures & lane.new_mutant_failures)
            for lane in LANES
        ))
        self.assertTrue(all(
            "build_live_agent" not in lane.good and "build_live_agent" not in lane.mutant
            for lane in LANES
        ))

    def rewrite(self, old: str, new: str):
        path = self.root / "scripts" / "ci.sh"
        content = path.read_text(encoding="utf-8")
        self.assertEqual(content.count(old), 1)
        path.write_text(content.replace(old, new), encoding="utf-8")

    def test_missing_historical_lane_is_a_failure(self):
        self.rewrite(
            "check helpdesk-langgraph baselines/helpdesk",
            "check discarded-helpdesk-langgraph baselines/helpdesk",
        )
        with self.assertRaisesRegex(AssertionError, "manifest drift"):
            verify_script_contract(self.root)

    def test_option_change_is_a_failure(self):
        self.rewrite(
            "--output-map examples.triage.agent:from_output",
            "--output-map examples.triage.agent:invented",
        )
        with self.assertRaisesRegex(AssertionError, "replay options do not match"):
            verify_script_contract(self.root)

    def test_absent_video_derived_dataset_is_a_failure(self):
        (self.root / BY_LABEL["orders-strands"].dataset).unlink()
        with self.assertRaisesRegex(AssertionError, "dataset missing"):
            verify_script_contract(self.root)

    def test_baseline_snapshot_detects_changes(self):
        folder = self.root / "temporary-generated-baseline"
        folder.mkdir()
        file = folder / "report.md"
        file.write_text("initial\n", encoding="utf-8")
        before = digests(folder)
        file.write_text("modified\n", encoding="utf-8")
        self.assertNotEqual(before, digests(folder))


if __name__ == "__main__":
    unittest.main()

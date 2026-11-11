"""Offline tests for the one-time safe reconstruction branch cleanup."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from reconstruction_tools.prune_obsolete_branches import (
    INTEGRATION, REPOSITORY, check_target, load_manifest,
)


class FakeGithub:
    def __init__(self, branch, pr=None, compare=None):
        self.branch = branch
        self.pr = pr
        self.compare = compare

    def repo(self, path, method="GET"):
        if "/branches/" in path:
            return self.branch
        if "/pulls/" in path:
            return self.pr
        if "/compare/" in path:
            return self.compare
        raise AssertionError("unexpected GitHub request " + path)


class SafeBranchPruneTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.base_sha = "b" * 40
        self.row = {
            "name": "reconstruction/sample-topic",
            "sha": self.sha,
            "reason": "merged_pr",
            "pr_number": 1,
        }
        self.branch = {"protected": False, "commit": {"sha": self.sha}}
        self.pr = {
            "merged_at": "2026-11-11T01:00:00Z",
            "head": {
                "ref": self.row["name"], "sha": self.sha,
                "repo": {"full_name": REPOSITORY},
            },
            "base": {"ref": INTEGRATION},
        }

    def test_manifest_requires_pinned_safe_names_and_expected_sha(self):
        rows = load_manifest()
        self.assertEqual(len(rows), 57)
        self.assertEqual(sum(r["reason"] == "merged_pr" for r in rows), 54)
        self.assertEqual(sum(r["reason"] == "ancestor" for r in rows), 3)
        self.assertNotIn("master", {r["name"] for r in rows})
        self.assertNotIn(INTEGRATION, {r["name"] for r in rows})
        self.assertNotIn("reconstruction/source-replayed-fixture-coverage-2026-11-06",
                         {r["name"] for r in rows})

    def test_invalid_manifest_fails_closed(self):
        base = json.loads(
            (Path(__file__).resolve().parents[1] /
             "reconstruction_manifest/branch_cleanup_2026-11-12.json").read_text(encoding="utf-8")
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            for mutation in (
                lambda doc: doc["targets"][0].update(name="../master"),
                lambda doc: doc["targets"][0].update(sha="0"),
                lambda doc: doc["targets"].append(copy.deepcopy(doc["targets"][0])),
                lambda doc: doc["targets"][0].update(reason="manual"),
            ):
                doc = copy.deepcopy(base)
                mutation(doc)
                path.write_text(json.dumps(doc), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_manifest(path)

    def test_merged_pr_is_eligible_only_when_source_matches(self):
        api = FakeGithub(self.branch, self.pr)
        self.assertEqual(check_target(api, self.row, set(), self.base_sha), "eligible")
        changed = copy.deepcopy(self.pr)
        changed["head"]["sha"] = "c" * 40
        self.assertIn("PR provenance", check_target(
            FakeGithub(self.branch, changed), self.row, set(), self.base_sha
        ))

    def test_open_pr_protected_or_moved_branch_is_not_deleted(self):
        api = FakeGithub(self.branch, self.pr)
        self.assertIn("open pull request", check_target(
            api, self.row, {self.row["name"]}, self.base_sha
        ))
        self.assertIn("branch rule", check_target(
            FakeGithub({"protected": True, "commit": {"sha": self.sha}}, self.pr),
            self.row, set(), self.base_sha,
        ))
        self.assertIn("branch changed", check_target(
            FakeGithub({"protected": False, "commit": {"sha": "c" * 40}}, self.pr),
            self.row, set(), self.base_sha,
        ))

    def test_ancestor_requires_zero_unique_commits(self):
        row = {k: v for k, v in self.row.items() if k != "pr_number"}
        row["reason"] = "ancestor"
        self.assertEqual(check_target(
            FakeGithub(self.branch, compare={"status": "behind", "ahead_by": 0}),
            row, set(), self.base_sha), "eligible")
        self.assertIn("no longer proven ancestor", check_target(
            FakeGithub(self.branch, compare={"status": "diverged", "ahead_by": 2}),
            row, set(), self.base_sha))

    def test_missing_branch_is_noop(self):
        self.assertEqual(
            check_target(FakeGithub(None, self.pr), self.row, set(), self.base_sha),
            "already absent",
        )


if __name__ == "__main__":
    unittest.main()

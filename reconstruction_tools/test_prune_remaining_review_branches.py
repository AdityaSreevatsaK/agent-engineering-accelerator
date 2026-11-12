"""Offline guards for the final reconstruction review-branch cleanup."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from reconstruction_tools.prune_remaining_review_branches import (
    BASE, MANIFEST, REPO, inspect, load_manifest,
)


class FakeGithub:
    def __init__(self, entries: dict):
        self.entries = entries

    def repo(self, path: str, method: str = "GET"):
        if method != "GET":
            raise AssertionError("Offline tests must never delete branches")
        return self.entries.get(path)


class FinalBranchPruneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_manifest()

    def test_exactly_eight_reviewed_and_pinned_targets(self):
        self.assertEqual(len(self.rows), 8)
        self.assertEqual(sum(r["reason"] == "identical" for r in self.rows), 3)
        self.assertEqual(sum(r["reason"] == "superseded" for r in self.rows), 4)
        self.assertEqual(sum(r["reason"] == "closed_superseded_pr" for r in self.rows), 1)
        self.assertNotIn(BASE, {r["name"] for r in self.rows})
        self.assertNotIn("master", {r["name"] for r in self.rows})

    def test_manifest_rejects_bad_reason_sha_branch_and_duplicates(self):
        original = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for key, value in (("name", "reconstruction/../../master"),
                           ("sha", "abc"), ("reason", "delete_everything")):
            data = copy.deepcopy(original)
            data["targets"][0][key] = value
            with TemporaryDirectory() as temp:
                path = Path(temp) / "bad.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_manifest(path)
        data = copy.deepcopy(original)
        data["targets"][1]["name"] = data["targets"][0]["name"]
        with TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_content_matches_current_and_reviewed_snapshots(self):
        row = next(r for r in self.rows if r["reason"] == "superseded")
        from urllib.parse import quote
        branch_path = "/branches/" + quote(row["name"], safe="/")
        old = "/contents/" + row["path"] + "?ref=" + quote(row["name"], safe="")
        new = "/contents/" + row["path"] + "?ref=" + quote(BASE, safe="")
        entries = {
            branch_path: {"protected": False, "commit": {"sha": row["sha"]}},
            old: {"sha": row["old_blob"]},
            new: {"sha": row["new_blob"]},
        }
        self.assertEqual(inspect(FakeGithub(entries), row, set()), "eligible")
        self.assertEqual(inspect(FakeGithub(entries), row, {row["name"]}), "skip: open PR")
        altered = copy.deepcopy(entries)
        altered[new]["sha"] = "0" * 40
        self.assertEqual(inspect(FakeGithub(altered), row, set()), "skip: integrated source changed")
        altered = copy.deepcopy(entries)
        altered[branch_path]["protected"] = True
        self.assertEqual(inspect(FakeGithub(altered), row, set()), "skip: protected branch or head changed")
        altered = copy.deepcopy(entries)
        altered[branch_path]["commit"]["sha"] = "0" * 40
        self.assertEqual(inspect(FakeGithub(altered), row, set()), "skip: protected branch or head changed")
        altered = copy.deepcopy(entries)
        altered[branch_path] = None
        self.assertEqual(inspect(FakeGithub(altered), row, set()), "already absent")

    def test_closed_pr33_must_remain_unmerged_and_replacements_unchanged(self):
        row = next(r for r in self.rows if r["reason"] == "closed_superseded_pr")
        from urllib.parse import quote
        entries = {
            "/branches/" + quote(row["name"], safe="/"): {
                "protected": False, "commit": {"sha": row["sha"]}
            },
            "/pulls/33": {
                "state": "closed", "merged_at": None,
                "head": {"ref": row["name"], "sha": row["sha"],
                         "repo": {"full_name": REPO}},
            },
        }
        for replacement in row["replacements"]:
            entries["/contents/" + replacement["path"] + "?ref=" + quote(BASE, safe="")] = {
                "sha": replacement["blob"]
            }
        self.assertEqual(inspect(FakeGithub(entries), row, set()), "eligible")
        changed = copy.deepcopy(entries)
        changed["/pulls/33"]["state"] = "open"
        self.assertIn("PR no longer closed", inspect(FakeGithub(changed), row, set()))
        changed = copy.deepcopy(entries)
        changed["/pulls/33"]["merged_at"] = "2026-11-12T18:00:00Z"
        self.assertIn("PR no longer closed", inspect(FakeGithub(changed), row, set()))
        changed = copy.deepcopy(entries)
        last = row["replacements"][0]
        changed["/contents/" + last["path"] + "?ref=" + quote(BASE, safe="")]["sha"] = "1" * 40
        self.assertEqual(inspect(FakeGithub(changed), row, set()), "skip: replacement code changed")


if __name__ == "__main__":
    unittest.main()

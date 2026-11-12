"""Safely remove eight superseded reconstruction review branches.

The manifest records exact commit and file-blob identities. The CI workflow
validates original-branch and current integration file hashes, closed PR
status, open PRs, branch protection and head changes before every deletion.
No historic files, production branch, original fixtures, or model services
are changed. This is NOT a release-readiness endorsement.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote

from reconstruction_tools.prune_obsolete_branches import Github

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reconstruction_manifest" / "branch_cleanup_2026-11-12_final.json"
REPO = "AdityaSreevatsaK/agent-engineering-accelerator"
BASE = "reconstruction/wip-checkpoint-2026-10-30"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_NAME = re.compile(r"^reconstruction/[a-zA-Z0-9._/-]+$")


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if (obj.get("schema") != "aea-final-branch-cleanup-v1"
            or obj.get("repository") != REPO
            or obj.get("integration_branch") != BASE
            or obj.get("excluded") != ["master", BASE]):
        raise ValueError("Unexpected final cleanup manifest identity")
    rows = obj.get("targets")
    if not isinstance(rows, list) or len(rows) != 8:
        raise ValueError("Expected exactly eight reviewed branch targets")
    names = set()
    for r in rows:
        name, sha, reason = r.get("name"), r.get("sha"), r.get("reason")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or ".." in name or "//" in name or name == BASE:
            raise ValueError("Unsafe or excluded branch")
        if name in names or not isinstance(sha, str) or not SHA40.fullmatch(sha):
            raise ValueError(f"Duplicate name or invalid SHA: {name}")
        names.add(name)
        if reason in ("identical", "superseded"):
            if (not isinstance(r.get("path"), str)
                    or r["path"].startswith("/")
                    or ".." in r["path"]
                    or not all(isinstance(r.get(x), str) and SHA40.fullmatch(r[x])
                                for x in ("old_blob", "new_blob"))):
                raise ValueError(f"Missing content evidence for {name}")
            same = r["old_blob"] == r["new_blob"]
            if same != (reason == "identical"):
                raise ValueError(f"Incorrect identical/superseded classification for {name}")
        elif reason == "closed_superseded_pr":
            if r.get("pr_number") != 33 or not isinstance(r.get("replacements"), list) or len(r["replacements"]) != 2:
                raise ValueError(f"Unrecognised closed PR archive for {name}")
            for f in r["replacements"]:
                if not isinstance(f.get("path"), str) or ".." in f["path"] or not SHA40.fullmatch(str(f.get("blob", ""))):
                    raise ValueError("Unsafe replacement path/blob")
        else:
            raise ValueError(f"Unknown reason: {reason}")
    if sum(r["reason"] == "closed_superseded_pr" for r in rows) != 1:
        raise ValueError("Exactly one closed superseded PR expected")
    return rows


def checked_blob(client: Github, path: str, ref: str) -> str | None:
    data = client.repo("/contents/" + quote(path, safe="/") + "?ref=" + quote(ref, safe=""))
    return data.get("sha") if isinstance(data, dict) else None


def open_pr_heads(client: Github) -> set[str]:
    rows = client.repo("/pulls?state=open&per_page=100")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise ValueError("Open PR response incomplete or untrusted")
    return {
        p["head"]["ref"] for p in rows
        if (p.get("head") and (p["head"].get("repo") or {}).get("full_name") == REPO)
    }


def inspect(client: Github, row: dict, current_open_heads: set[str]) -> str:
    name = row["name"]
    if name in current_open_heads:
        return "skip: open PR"
    entry = client.repo("/branches/" + quote(name, safe="/"))
    if entry is None:
        return "already absent"
    if entry.get("protected") or (entry.get("commit") or {}).get("sha") != row["sha"]:
        return "skip: protected branch or head changed"
    if row["reason"] in ("identical", "superseded"):
        if checked_blob(client, row["path"], name) != row["old_blob"]:
            return "skip: review branch source changed"
        if checked_blob(client, row["path"], BASE) != row["new_blob"]:
            return "skip: integrated source changed"
    else:
        pr = client.repo("/pulls/" + str(row["pr_number"]))
        head = (pr or {}).get("head") or {}
        if (not pr or pr.get("state") != "closed" or pr.get("merged_at")
                or head.get("ref") != name
                or head.get("sha") != row["sha"]
                or (head.get("repo") or {}).get("full_name") != REPO):
            return "skip: PR no longer closed, unmerged or tied to expected head"
        for entry in row["replacements"]:
            if checked_blob(client, entry["path"], BASE) != entry["blob"]:
                return "skip: replacement code changed"
    return "eligible"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true",
                        help="Offline manifest check without GitHub API or deletion")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path,
                        help="Save the exact delete/skip decisions as an audit JSON")
    args = parser.parse_args(argv)
    try:
        targets = load_manifest()
        print(f"SHA-pinned final cleanup manifest: {len(targets)} branches", flush=True)
        if args.validate_only:
            return 0
        if args.apply and (
            os.environ.get("GITHUB_REPOSITORY") != REPO
            or os.environ.get("GITHUB_EVENT_NAME") != "push"
            or os.environ.get("GITHUB_REF") != "refs/heads/" + BASE
        ):
            raise ValueError("Deletion only permitted from integration-branch push CI")
        client = Github(os.environ.get("GITHUB_TOKEN", ""))
        repo_info = client.repo("")
        if not repo_info or repo_info.get("default_branch") != "master":
            raise ValueError("Unexpected repository/default branch identity")
        integration = client.repo("/branches/" + quote(BASE, safe="/"))
        if not integration:
            raise ValueError("Integration branch is missing")
        decisions = []
        heads = open_pr_heads(client)
        for row in targets:
            result = inspect(client, row, heads)
            decisions.append({"name": row["name"], "result": result})
        print("Initial live preflight:", json.dumps({
            key: sum(x["result"] == key for x in decisions)
            for key in sorted(set(x["result"] for x in decisions))
        }), flush=True)
        if args.apply:
            if any(d["result"] not in ("eligible", "already absent") for d in decisions):
                raise ValueError("Initial live preflight not clean; refusing all deletions")
            for row, decision in zip(targets, decisions):
                if decision["result"] != "eligible":
                    continue
                # GitHub's ref deletion API has no SHA lease, so minimise the
                # race window by refetching both the PRs and branch evidence.
                decision["result"] = inspect(client, row, open_pr_heads(client))
                if decision["result"] != "eligible":
                    print(f"SKIPPED {row['name']}: {decision['result']}", flush=True)
                    continue
                client.repo("/git/refs/heads/" + quote(row["name"], safe="/"),
                            method="DELETE")
                decision["result"] = "deleted"
                print(f"DELETED {row['name']}", flush=True)
        counts = {
            key: sum(x["result"] == key for x in decisions)
            for key in sorted(set(x["result"] for x in decisions))
        }
        print("Final decisions:", json.dumps(counts, sort_keys=True), flush=True)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps({
                "schema": "aea-final-branch-cleanup-report-v1",
                "integration_sha": integration["commit"]["sha"],
                "apply": args.apply, "results": decisions, "counts": counts
            }, indent=2) + "\n", encoding="utf-8")
        if args.apply and any(d["result"] not in ("deleted", "already absent") for d in decisions):
            return 1
        return 0
    except (RuntimeError, ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"FINAL BRANCH CLEANUP REFUSED: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

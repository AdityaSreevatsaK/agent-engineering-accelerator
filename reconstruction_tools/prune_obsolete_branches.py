"""One-time, conservative cleanup of video-reconstruction topic branches.

Run locally without credentials:
    python -m reconstruction_tools.prune_obsolete_branches --validate-only

The GitHub Actions job is the only intended live deletion operator.
It checks an explicit branch SHA lease, historical merged PR or ancestry evidence,
current open PRs, and protected/default/integration branches before every DELETE.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reconstruction_manifest" / "branch_cleanup_2026-11-12.json"
REPOSITORY = "AdityaSreevatsaK/agent-engineering-accelerator"
INTEGRATION = "reconstruction/wip-checkpoint-2026-10-30"
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
BRANCH_RE = re.compile(r"^reconstruction/[A-Za-z0-9._/-]+$")


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("schema") != "aea-branch-cleanup-v1"
            or doc.get("repository") != REPOSITORY
            or doc.get("integration_branch") != INTEGRATION):
        raise ValueError("Unrecognised branch-cleanup manifest provenance")
    rows = doc.get("targets")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a non-empty explicit list of branch targets")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed cleanup target")
        name, sha, reason = row.get("name"), row.get("sha"), row.get("reason")
        if not isinstance(name, str) or not BRANCH_RE.fullmatch(name):
            raise ValueError("Unsafe branch name")
        if name in (INTEGRATION, "master") or "//" in name or "/../" in name or name.endswith("/"):
            raise ValueError(f"Excluded branch: {name}")
        if name in seen:
            raise ValueError(f"Duplicate branch: {name}")
        seen.add(name)
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise ValueError(f"Invalid branch SHA: {name}")
        if reason == "merged_pr":
            if type(row.get("pr_number")) is not int or row["pr_number"] < 1:
                raise ValueError(f"Missing merged PR identifier: {name}")
        elif reason == "ancestor":
            if "pr_number" in row:
                raise ValueError(f"Unexpected PR identifier for ancestor: {name}")
        else:
            raise ValueError(f"Unsafe deletion reason: {reason}")
    return rows


class Github:
    def __init__(self, token: str):
        if not token:
            raise ValueError("Missing GITHUB_TOKEN; live operations require CI credentials")
        self.token = token

    def request(self, path: str, method: str = "GET"):
        req = Request(
            "https://api.github.com" + path,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "AEA-safe-branch-cleanup",
            },
            method=method,
        )
        try:
            with urlopen(req, timeout=25) as resp:
                data = resp.read()
                return json.loads(data) if data else None
        except HTTPError as exc:
            if method == "GET" and exc.code == 404:
                return None
            raise RuntimeError(f"GitHub {method} {path}: HTTP {exc.code}") from exc

    def repo(self, path: str, method: str = "GET"):
        return self.request(f"/repos/{REPOSITORY}{path}", method=method)


def check_target(client: Github, row: dict, open_heads: set[str],
                 integration_sha: str) -> str:
    name, sha = row["name"], row["sha"]
    if name in open_heads:
        return "protected: open pull request"
    branch = client.repo("/branches/" + quote(name, safe="/"))
    if branch is None:
        return "already absent"
    if branch.get("protected"):
        return "protected: branch rule"
    if branch.get("commit", {}).get("sha") != sha:
        return "protected: branch changed since review"
    if row["reason"] == "merged_pr":
        pr = client.repo("/pulls/" + str(row["pr_number"]))
        if not pr or not pr.get("merged_at"):
            return "protected: PR has no confirmed merge"
        head = pr.get("head") or {}
        repo = head.get("repo") or {}
        if (head.get("ref") != name or head.get("sha") != sha
                or repo.get("full_name") != REPOSITORY
                or (pr.get("base") or {}).get("ref") not in (INTEGRATION, "master")):
            return "protected: PR provenance differs"
    else:
        compare = client.repo("/compare/" + integration_sha + "..." + sha)
        if (not compare or compare.get("ahead_by") != 0
                or compare.get("status") not in ("behind", "identical")):
            return "protected: branch no longer proven ancestor"
    return "eligible"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--validate-only", action="store_true",
                   help="Offline manifest structural tests; never contacts GitHub")
    p.add_argument("--apply", action="store_true",
                   help="Delete eligible pinned refs, only on integration push in GitHub Actions")
    p.add_argument("--report", type=Path, help="Write JSON audit outside tracked checkout")
    args = p.parse_args(argv)
    try:
        rows = load_manifest()
        print(f"Manifest: {len(rows)} pinned branches ({sum(x['reason']=='merged_pr' for x in rows)} merged PRs); master and integration excluded")
        if args.validate_only:
            return 0
        if args.apply and (
            os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_EVENT_NAME") != "push"
            or os.environ.get("GITHUB_REF") != "refs/heads/" + INTEGRATION
        ):
            raise ValueError("Deletion is restricted to the integration-branch push workflow")
        client = Github(os.environ.get("GITHUB_TOKEN", ""))
        integration = client.repo("/branches/" + quote(INTEGRATION, safe="/"))
        if not integration:
            raise ValueError("Integration branch does not exist")
        current_sha = integration["commit"]["sha"]
        open_prs = client.repo("/pulls?state=open&per_page=100")
        if not isinstance(open_prs, list) or len(open_prs) >= 100:
            raise ValueError("Open PR list incomplete; refusing branch deletions")
        open_heads = {
            p["head"]["ref"]
            for p in open_prs
            if p.get("head") and (p["head"].get("repo") or {}).get("full_name") == REPOSITORY
        }
        decisions = []
        for row in rows:
            decision = check_target(client, row, open_heads, current_sha)
            decisions.append({"name": row["name"], "result": decision})
        eligible = sum(d["result"] == "eligible" for d in decisions)
        print(f"Live preflight: {eligible} eligible, {len(decisions)-eligible} skipped")
        if args.apply:
            for decision in decisions:
                if decision["result"] != "eligible":
                    continue
                row = next(r for r in rows if r["name"] == decision["name"])
                # Re-read PR list and branch head to avoid deleting a ref changed
                # after the initial evaluation.
                latest_prs = client.repo("/pulls?state=open&per_page=100")
                if not isinstance(latest_prs, list) or len(latest_prs) >= 100:
                    raise ValueError("Open PR list changed/incomplete; stop deletions")
                latest_heads = {
                    p["head"]["ref"] for p in latest_prs
                    if p.get("head") and (p["head"].get("repo") or {}).get("full_name") == REPOSITORY
                }
                current = check_target(client, row, latest_heads, current_sha)
                if current != "eligible":
                    decision["result"] = current
                    continue
                client.repo("/git/refs/heads/" + quote(row["name"], safe="/"), method="DELETE")
                decision["result"] = "deleted"
                print(f"DELETED {row['name']}")
        summary = {status: sum(d["result"] == status for d in decisions)
                   for status in sorted(set(d["result"] for d in decisions))}
        print("Final results:", json.dumps(summary, sort_keys=True))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps({
                "schema": "aea-branch-cleanup-report-v1",
                "integration_sha": current_sha,
                "apply": args.apply,
                "results": decisions,
                "counts": summary,
            }, indent=2) + "\n", encoding="utf-8")
        if args.apply and any(d["result"] == "eligible" for d in decisions):
            return 1
        return 0
    except (ValueError, OSError, RuntimeError, URLError, KeyError, json.JSONDecodeError) as exc:
        print(f"BRANCH CLEANUP REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

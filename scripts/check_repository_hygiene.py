"""Check the current tracked source tree for retired process artefacts and wording."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Split tokens keep this guard from matching its own source.
DISALLOWED = (
    "recon" + "struction",
    "screen" + "shot",
    "vid" + "eo",
    "trans" + "cription",
    "histo" + "rical",
    "recover" + "ed",
    "foot" + "age",
)
MEDIA_SUFFIXES = (".web" + "m", ".m" + "p4", ".m" + "ov")


def main() -> int:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    names = [item.decode("utf-8") for item in tracked.split(b"\0") if item]
    bad: list[str] = []
    for name in names:
        relative = name.lower()
        if any(term in relative for term in DISALLOWED) or relative.endswith(MEDIA_SUFFIXES):
            bad.append(f"{name}: path")
        path = ROOT / name
        if not path.is_file():
            bad.append(f"{name}: missing")
            continue
        content = path.read_bytes().decode("utf-8", errors="ignore").lower()
        for term in DISALLOWED:
            if term in content:
                bad.append(f"{name}: stale token")
                break
    if bad:
        print("Unexpected retired artefacts or wording in tracked files:", file=sys.stderr)
        for finding in bad:
            print("  " + finding, file=sys.stderr)
        return 1
    print(f"PASS: {len(names)} tracked files have clean paths and content")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify user-video and screenshot-derived AEA helpdesk sources.

Original evidence: two complete Notepad++ screen recordings for Python
modules and three screenshots covering all ten dataset and six golden entries.

Video dimensions: agent.py 225 displayed LF lines, 9,818 characters;
rules.py 225 displayed Windows CRLF lines, 9,963 characters.
Recovered rules candidate is 2 CRLF-equivalent characters LONGER than video;
this is a known fidelity gap, not corrected by padding or altered tests.

Never claim byte-identical historical originals.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples" / "helpdesk"

CODE = {
    "agent.py": ("e27f99efecda2301cf76e04f15e6a429b827538ef13588697e8652453f53103b", 9818, 225, 9818),
    "rules.py": ("dfec7b546ae650267d1a57ab519dc4980f164cde19830f773ced0de6dcd86886", 9741, 225, 9963),
}
DATA = {
    "dataset.jsonl": ("56697e5cc1eb24576b8a780fe7cf986827635fc0cb20fa6eda95db418932986d", 10),
    "golden.jsonl": ("0e795600ff4bc69872e31a810c1838b2291537d6a51ff5442ff01f46c56cd372", 6),
}
DATASET_IDS = (
    "device_status_low_disk", "device_status_offline", "device_unknown",
    "device_id_missing", "password_reset", "password_unknown_user",
    "admin_local_docker", "admin_driver_update",
    "out_of_scope_meeting_room", "out_of_scope_expenses",
)
GOLDEN_IDS = (
    "device_status_low_disk", "device_status_offline", "device_unknown",
    "password_reset", "password_unknown_user", "out_of_scope_meeting_room",
)


def verify() -> None:
    for name, (sha, size, displayed_lines, editor_length) in CODE.items():
        source = (BASE / name).read_text(encoding="utf-8")
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != sha:
            raise AssertionError(f"{name}: original video candidate has been changed")
        if len(source) != size or source.count("\n") + 1 != displayed_lines or not source.endswith("\n"):
            raise AssertionError(f"{name}: recorded source dimensions changed")
        ast.parse(source, filename=str(BASE / name), feature_version=(3, 11))
        converted = len(source) + (source.count("\n") if name == "rules.py" else 0)
        delta = converted - editor_length
        if delta != (2 if name == "rules.py" else 0):
            raise AssertionError(f"{name}: unexpected video-vs-candidate difference: {delta:+d}")
        print(f"{name}: {displayed_lines} editor lines; {converted} reconstructed editor chars; "
              f"video {editor_length} ({delta:+d}); syntax and pinned hash OK")

    loaded: dict[str, list[dict]] = {}
    for name, (sha, number) in DATA.items():
        raw = (BASE / name).read_text(encoding="utf-8")
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != sha:
            raise AssertionError(f"{name}: original screenshot transcription has changed")
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if len(rows) != number or not raw.endswith("\n"):
            raise AssertionError(f"{name}: unexpected record count")
        if len({row["id"] for row in rows}) != number:
            raise AssertionError(f"{name}: duplicate IDs")
        loaded[name] = rows
    assert tuple(x["id"] for x in loaded["dataset.jsonl"]) == DATASET_IDS
    assert tuple(x["id"] for x in loaded["golden.jsonl"]) == GOLDEN_IDS
    assert sum(x.get("label") == "pass" for x in loaded["golden.jsonl"]) == 5
    assert sum(x.get("expect_interrupt") is True for x in loaded["dataset.jsonl"]) == 2
    for row in loaded["golden.jsonl"]:
        if set(row) - {"id", "reference", "label", "notes"}:
            raise AssertionError(f"Unexpected golden field: {row['id']}")
    print("Screenshot candidates: ten helpdesk dataset cases, six golden references (five labelled).")
    print("Video and screenshot candidates validated; historical-byte identity not established.")


if __name__ == "__main__":
    verify()

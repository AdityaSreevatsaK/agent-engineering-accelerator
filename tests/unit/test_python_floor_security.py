"""Guard the supported Python floor and removal of the vulnerable SoupSieve alternative.

The previous uv.lock selected soupsieve==2.10 for CPython 3.11.0-3.11.4,
with three published 2026 advisories. Do not silently reintroduce that range.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_supported_python_floor_matches_lock_after_security_remediation():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert project["project"]["requires-python"] == ">=3.11.5"
    assert lock["requires-python"] == ">=3.11.5"


def test_no_known_vulnerable_old_soupsieve_resolution():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {p["version"] for p in lock["package"] if p["name"] == "soupsieve"}
    assert versions == {"4.1"}
    assert all(p["name"] != "soupsieve" or p["version"] != "2.10" for p in lock["package"])

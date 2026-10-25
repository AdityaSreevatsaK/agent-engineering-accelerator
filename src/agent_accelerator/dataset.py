"""Versioned JSONL dataset format: one evaluation case per line."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DATASET_FORMAT_VERSION = 1


class ExpectedToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    match: Literal["exact", "subset"] = "exact"


class ExpectedToolArgs(BaseModel):
    """Some call to `tool` has at least these arguments (a subset match)."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class Case(BaseModel):
    """One evaluation case. Every expectation is optional; only the ones present are checked."""

    model_config = ConfigDict(extra="forbid")

    id: str
    input: str
    expected_output: str | None = None
    output_contains: list[str] | None = None
    output_not_contains: list[str] | None = None
    expected_json_schema: dict[str, Any] | None = None
    # None means "not checked"; an empty list means "no tool may be called".
    expected_tool_calls: list[ExpectedToolCall] | None = None
    allow_extra_tool_calls: bool = False
    # Trajectory checks: independent of expected_tool_calls, each scored separately.
    expected_tools: list[str] | None = None  # each called at least once
    tool_order: list[str] | None = None  # called in this relative order; other calls may interleave
    forbidden_tools: list[str] | None = None  # none of them called
    max_tool_calls: int | None = Field(default=None, ge=0)
    expected_tool_args: list[ExpectedToolArgs] | None = None
    # None means "not checked", but an interrupted run fails unless this is true. LangGraph only.
    expect_interrupt: bool | None = None
    config: dict[str, Any] | None = None  # LangGraph only: merged into the run's "configurable"
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_dataset(path: Path) -> list[Case]:
    cases: list[Case] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(Case.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"{path}:{line_no}: invalid case: {exc}") from exc
    ids = [c.id for c in cases]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate case ids: {', '.join(duplicates)}")
    if not cases:
        raise ValueError(f"{path}: dataset is empty")
    return cases


def dataset_sha256(path: Path) -> str:
    """Line endings are normalized so a Windows checkout (CRLF) hashes the same as the committed file (LF)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def case_from_metadata(metadata: dict[str, Any]) -> Case:
    return Case.model_validate(metadata["case"])


def case_to_metadata(case: Case) -> dict[str, Any]:
    return {"case": json.loads(case.model_dump_json())}

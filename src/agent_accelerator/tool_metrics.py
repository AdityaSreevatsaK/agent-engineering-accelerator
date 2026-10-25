"""Tool-use metrics: recorded per epoch at score time, aggregated per case and per run for the report.

Only tool names, counts and ratios are recorded. Arguments are compared through a hash computed at score
time and discarded, so nothing here carries a payload and the metadata survives the scrub unchanged.
"""

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from inspect_ai.scorer import Score

from agent_accelerator.dataset import Case


def _call_hash(call: dict[str, Any]) -> str:
    """Digest of a call's name and arguments; key order does not matter."""
    payload = json.dumps([call["name"], call.get("arguments")], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def redundant_calls(calls: list[dict[str, Any]]) -> int:
    """Calls that repeat an earlier call in the same epoch with the same name and arguments."""
    seen: set[str] = set()
    repeats = 0
    for call in calls:
        digest = _call_hash(call)
        repeats += digest in seen
        seen.add(digest)
    return repeats


def expected_tool_names(case: Case) -> set[str] | None:
    """Tools the case expects to be called, from expected_tool_calls and expected_tools; None if it declares none."""
    if case.expected_tool_calls is None and case.expected_tools is None:
        return None
    return {c.name for c in case.expected_tool_calls or []} | set(case.expected_tools or [])


def selection(called: Iterable[str], expected: set[str]) -> tuple[float | None, float | None]:
    """(precision, recall) of the distinct called tools against the expected set; None where undefined."""
    distinct = set(called)
    hits = len(distinct & expected)
    precision = hits / len(distinct) if distinct else None
    recall = hits / len(expected) if expected else None
    return precision, recall


def score_metadata(case: Case, calls: list[dict[str, Any]] | None, errors: list[bool | None] | None) -> dict[str, Any]:
    """Case_checks score metadata for one epoch. errors[i] is whether call i's result was an error (None: no result).

    Empty when the adapter recorded no calls list, so older logs and such adapters show no tool-use data.
    """
    if calls is None:
        return {}
    names = [call["name"] for call in calls]
    flags = errors if errors is not None and len(errors) == len(calls) else [None] * len(calls)
    metadata: dict[str, Any] = {
        "tool_names": names,
        "tool_results": sum(f is not None for f in flags),  # calls whose outcome is known
        "tool_errors": sum(f is True for f in flags),
        "redundant_tool_calls": redundant_calls(calls),
    }
    expected = expected_tool_names(case)
    if expected is not None:
        metadata["tool_precision"], metadata["tool_recall"] = selection(names, expected)
    return metadata


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


@dataclass(frozen=True)
class CaseToolUse:
    """One case's tool use over the epochs that recorded it."""

    calls_per_epoch: tuple[int, ...]
    by_tool: dict[str, int]  # calls per tool name, summed over epochs
    results: int  # calls whose outcome the adapter recorded
    errors: int
    redundant: int
    precision: float | None  # per-epoch mean; None when the case declares no expected tools or it is undefined
    recall: float | None


def case_tool_use(scores: Iterable[Score | None]) -> CaseToolUse | None:
    """From each epoch's case_checks score; None when no epoch recorded tool names."""
    metadata = [s.metadata or {} for s in scores if s is not None]
    epochs = [m for m in metadata if isinstance(m.get("tool_names"), list)]
    if not epochs:
        return None
    by_tool = Counter(str(name) for m in epochs for name in m["tool_names"])
    precisions = [float(p) for m in epochs if isinstance(p := m.get("tool_precision"), int | float)]
    recalls = [float(r) for m in epochs if isinstance(r := m.get("tool_recall"), int | float)]
    return CaseToolUse(
        calls_per_epoch=tuple(len(m["tool_names"]) for m in epochs),
        by_tool=dict(by_tool),
        results=sum(int(m.get("tool_results") or 0) for m in epochs),
        errors=sum(int(m.get("tool_errors") or 0) for m in epochs),
        redundant=sum(int(m.get("redundant_tool_calls") or 0) for m in epochs),
        precision=_mean(precisions),
        recall=_mean(recalls),
    )


@dataclass
class RunToolUse:
    calls_per_epoch: list[int]  # one entry per case-epoch
    by_tool: Counter[str] = field(default_factory=Counter)
    results: int = 0
    errors: int = 0
    redundant: int = 0
    precision: float | None = None  # macro-average over cases that declare expected tools
    recall: float | None = None
    selection_cases: int = 0

    @property
    def total(self) -> int:
        return sum(self.calls_per_epoch)


def run_tool_use(cases: Iterable[CaseToolUse | None]) -> RunToolUse | None:
    """None when no case recorded any tool call."""
    recorded = [c for c in cases if c is not None]
    if not any(sum(c.calls_per_epoch) for c in recorded):
        return None
    by_tool: Counter[str] = Counter()
    for c in recorded:
        by_tool.update(c.by_tool)
    precisions = [c.precision for c in recorded if c.precision is not None]
    recalls = [c.recall for c in recorded if c.recall is not None]
    return RunToolUse(
        calls_per_epoch=[n for c in recorded for n in c.calls_per_epoch],
        by_tool=by_tool,
        results=sum(c.results for c in recorded),
        errors=sum(c.errors for c in recorded),
        redundant=sum(c.redundant for c in recorded),
        precision=_mean(precisions),
        recall=_mean(recalls),
        selection_cases=sum(c.precision is not None or c.recall is not None for c in recorded),
    )


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def tool_use_lines(cases: Iterable[CaseToolUse | None], top: int = 10) -> list[str]:
    """The run report's Tool use section; empty when no case recorded a tool call."""
    run = run_tool_use(cases)
    if run is None:
        return []
    counts = run.calls_per_epoch
    errors = (
        f"{run.errors}/{run.results} calls with a recorded result ({run.errors / run.results:.1%})"
        if run.results
        else "not recorded by the adapter"
    )
    selection_line = (
        f"precision {_pct(run.precision)}, recall {_pct(run.recall)} (macro over {run.selection_cases} case(s))"
        if run.selection_cases
        else "n/a (no case declares expected tools)"
    )
    lines = [
        "",
        "## Tool use (informational)",
        "",
        f"- Calls: {run.total} over {len(counts)} case-epoch(s); per case-epoch mean "
        f"{_number(run.total / len(counts))}, median {_number(median(counts))}, max {max(counts)}",
        f"- Tool errors: {errors}",
        f"- Redundant calls (same name and arguments as an earlier call in the epoch): "
        f"{run.redundant}/{run.total} ({run.redundant / run.total:.1%})",
        f"- Tool selection vs expected tools: {selection_line}",
        "",
        "| Tool | Calls | Share |",
        "|------|-------|-------|",
    ]
    ranked = sorted(run.by_tool.items(), key=lambda item: (-item[1], item[0]))
    for name, n in ranked[:top]:
        cell = name.replace("|", "\\|")  # names come from the agent's tool list; keep the table intact
        lines.append(f"| {cell} | {n} | {n / run.total:.1%} |")
    if len(ranked) > top:
        rest = sum(n for _, n in ranked[top:])
        lines.append(f"| {len(ranked) - top} other tool(s) | {rest} | {rest / run.total:.1%} |")
    return lines

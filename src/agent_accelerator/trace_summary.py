"""Framework-neutral summary of a run's traces: per case and epoch, model calls, tool calls and where the time went.

Strands (gen_ai.* attributes) and LangGraph (OpenInference) name their spans differently; this maps both onto
one shape. Informational only: scoring and comparison never read traces.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_SPAN = "eval_case"


@dataclass
class TraceSummary:
    sample_id: str
    epoch: int
    model_calls: int = 0
    tool_calls: list[str] = field(default_factory=list)  # tool names, in call order
    tool_errors: int = 0
    model_time_s: float = 0.0
    tool_time_s: float = 0.0
    total_time_s: float = 0.0


def _kind(attributes: dict[str, Any]) -> str | None:
    """'model', 'tool' or None, from Strands' gen_ai.operation.name or OpenInference's span kind."""
    operation = attributes.get("gen_ai.operation.name")
    span_kind = attributes.get("openinference.span.kind")
    if operation == "chat" or span_kind == "LLM":
        return "model"
    if operation == "execute_tool" or span_kind == "TOOL":
        return "tool"
    return None


def _duration_s(span: dict[str, Any]) -> float:
    return (datetime.fromisoformat(span["end_time"]) - datetime.fromisoformat(span["start_time"])).total_seconds()


def summarise_traces(path: Path) -> list[TraceSummary]:
    """One summary per eval_case root span, sorted by sample_id then epoch. Spans outside a case are ignored."""
    spans = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_trace: dict[str, list[dict[str, Any]]] = {}
    for span in spans:
        by_trace.setdefault(span["context"]["trace_id"], []).append(span)
    summaries = []
    for trace_spans in by_trace.values():
        root = next((s for s in trace_spans if s["name"] == ROOT_SPAN), None)
        if root is None:
            continue
        summary = TraceSummary(
            sample_id=str(root["attributes"]["eval.sample_id"]),
            epoch=int(root["attributes"].get("eval.epoch", 1)),
            total_time_s=_duration_s(root),
        )
        for span in sorted(trace_spans, key=lambda s: s["start_time"]):
            kind = _kind(span["attributes"])
            if kind == "model":
                summary.model_calls += 1
                summary.model_time_s += _duration_s(span)
            elif kind == "tool":
                summary.tool_calls.append(
                    span["attributes"].get("gen_ai.tool.name") or span["attributes"].get("tool.name") or span["name"]
                )
                summary.tool_errors += span.get("status", {}).get("status_code") == "ERROR"
                summary.tool_time_s += _duration_s(span)
        summaries.append(summary)
    return sorted(summaries, key=lambda s: (s.sample_id, s.epoch))

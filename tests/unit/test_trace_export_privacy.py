"""Test default OpenTelemetry payload redaction and explicit opt-in capture."""
from __future__ import annotations

import json
from pathlib import Path

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode

from agent_accelerator.trace_summary import summarise_traces
from agent_accelerator.tracing import JsonlSpanExporter

SENTINEL = "AEA-SYNTHETIC-SECRET-DO-NOT-PERSIST-f91c4"


def write_fixture(path: Path, redact: bool) -> None:
    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(JsonlSpanExporter(path, redact_errors=redact))
    )
    tracer = provider.get_tracer("aea-privacy-regression")
    with tracer.start_as_current_span("eval_case") as root:
        root.set_attribute("eval.sample_id", "synthetic-case-1")
        root.set_attribute("eval.epoch", 1)
        root.set_attribute("custom.request_input", SENTINEL)
        root.set_attribute("gen_ai.input.messages", SENTINEL)
        root.add_event(
            "custom event with " + SENTINEL,
            {"custom.tool_result": SENTINEL},
        )
        with tracer.start_as_current_span("synthetic-model"):
            from opentelemetry import trace
            trace.get_current_span().set_attribute("gen_ai.operation.name", "chat")
            trace.get_current_span().set_attribute("llm.prompt", SENTINEL)
        with tracer.start_as_current_span("synthetic-tool") as child:
            child.set_attribute("gen_ai.operation.name", "execute_tool")
            child.set_attribute("gen_ai.tool.name", "search")
            child.set_attribute("custom.parameters", SENTINEL)
            child.record_exception(ValueError(SENTINEL))
            child.set_status(Status(StatusCode.ERROR, SENTINEL))
    provider.shutdown()


def test_default_traces_do_not_store_arbitrary_span_attributes_or_events(tmp_path: Path) -> None:
    path = tmp_path / "default.jsonl"
    write_fixture(path, redact=True)
    raw = path.read_text(encoding="utf-8")
    assert SENTINEL not in raw
    spans = [json.loads(x) for x in raw.splitlines()]
    assert len(spans) == 3
    root = next(s for s in spans if s["name"] == "eval_case")
    assert root["attributes"] == {"eval.sample_id": "synthetic-case-1", "eval.epoch": 1}
    custom_event = root["events"][0]
    assert custom_event["name"] == "[REDACTED]"
    assert custom_event["attributes"] == {}
    assert not root.get("resource")
    assert not root.get("instrumentation_scope")
    tool = next(s for s in spans if s["name"] == "synthetic-tool")
    exception = next(event for event in tool["events"] if event["name"] == "exception")
    assert exception["attributes"]["exception.type"] == "ValueError"
    assert exception["attributes"]["exception.message"] == "[REDACTED]"
    assert tool["status"]["description"] == "[REDACTED]"


def test_default_traces_still_support_model_tool_duration_summary(tmp_path: Path) -> None:
    path = tmp_path / "default.jsonl"
    write_fixture(path, redact=True)
    [summary] = summarise_traces(path)
    assert summary.sample_id == "synthetic-case-1"
    assert summary.epoch == 1
    assert summary.model_calls == 1
    assert summary.tool_calls == ["search"]
    assert summary.tool_errors == 1


def test_explicit_capture_still_retains_attributes_and_custom_events(tmp_path: Path) -> None:
    path = tmp_path / "capture.jsonl"
    write_fixture(path, redact=False)
    raw = path.read_text(encoding="utf-8")
    assert SENTINEL in raw
    spans = [json.loads(x) for x in raw.splitlines()]
    assert any("custom.request_input" in s.get("attributes", {}) for s in spans)
    assert any(
        SENTINEL in event.get("name", "")
        for span in spans
        for event in span.get("events", [])
    )

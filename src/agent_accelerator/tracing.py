"""Local OpenTelemetry trace capture to a JSONL file.

Must run before the orchestration framework creates its tracer, because frameworks such as
Strands read the redaction setting once at tracer creation.
"""

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

# Strands: the empty allow-list after "=" redacts every sensitive gen_ai attribute.
_STRANDS_REDACT_ALL = "gen_ai_latest_experimental,gen_ai_unredacted_attributes="
_STRANDS_CAPTURE_ALL = "gen_ai_latest_experimental"
_OPENINFERENCE_HIDE = (
    "OPENINFERENCE_HIDE_INPUTS",
    "OPENINFERENCE_HIDE_OUTPUTS",
    "OPENINFERENCE_HIDE_INPUT_MESSAGES",
    "OPENINFERENCE_HIDE_OUTPUT_MESSAGES",
    "OPENINFERENCE_HIDE_LLM_TOOLS",
    "OPENINFERENCE_HIDE_LLM_INVOCATION_PARAMETERS",
)


_REDACTED = "[REDACTED]"
_EXCEPTION_TEXT = ("exception.message", "exception.stacktrace")


def _redact_errors(span: dict[str, Any]) -> dict[str, Any]:
    """Frameworks record exception messages and tracebacks, which can quote user data; keep only the type."""
    if span.get("status", {}).get("description"):
        span["status"]["description"] = _REDACTED
    for event in span.get("events", []):
        attributes = event.get("attributes", {})
        for key in _EXCEPTION_TEXT:
            if key in attributes:
                attributes[key] = _REDACTED
    return span


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path: Path, redact_errors: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file: IO[str] = path.open("a", encoding="utf-8")
        self._redact_errors = redact_errors

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            record = json.loads(span.to_json(indent=None))
            if self._redact_errors:
                record = _redact_errors(record)
            self._file.write(json.dumps(record) + "\n")
        self._file.flush()
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self._file.close()


def configure_tracing(path: Path, capture_content: bool) -> TracerProvider:
    os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = _STRANDS_CAPTURE_ALL if capture_content else _STRANDS_REDACT_ALL
    # OpenInference (LangGraph adapter): inputs cover prompts and tool arguments, outputs cover replies and results.
    for name in _OPENINFERENCE_HIDE:
        os.environ[name] = "false" if capture_content else "true"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(path, redact_errors=not capture_content)))
    trace.set_tracer_provider(provider)
    return provider

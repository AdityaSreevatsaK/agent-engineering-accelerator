import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode

from agent_accelerator.tracing import JsonlSpanExporter


def export_span(path, name, *, redact_errors, record_error=True):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(path, redact_errors=redact_errors)))

    with provider.get_tracer("tests").start_as_current_span(name) as span:
        if record_error:
            span.record_exception(ValueError("secret text"))
            span.set_status(Status(StatusCode.ERROR, "secret text"))

    provider.shutdown()


def read_exported_spans(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_jsonl_span_exporter_writes_json_lines_with_span_names(tmp_path):
    path = tmp_path / "spans.jsonl"

    export_span(path, "named-span", redact_errors=False)

    spans = read_exported_spans(path)
    assert len(spans) == 1
    assert spans[0]["name"] == "named-span"


def test_jsonl_span_exporter_redacts_exception_and_status_messages(tmp_path):
    path = tmp_path / "spans.jsonl"

    export_span(path, "redacted-span", redact_errors=True)

    content = path.read_text(encoding="utf-8")
    span = read_exported_spans(path)[0]
    exception_event = next(event for event in span["events"] if event["name"] == "exception")
    exception_attributes = exception_event["attributes"]

    assert "secret text" not in content
    assert exception_attributes["exception.type"] == "ValueError"
    assert exception_attributes["exception.message"] == "[REDACTED]"
    assert exception_attributes["exception.stacktrace"] == "[REDACTED]"
    assert span["status"]["description"] == "[REDACTED]"
    assert span["status"]["status_code"] == "ERROR"


def test_jsonl_span_exporter_keeps_error_messages_when_redaction_is_disabled(tmp_path):
    path = tmp_path / "spans.jsonl"

    export_span(path, "visible-span", redact_errors=False)

    assert "secret text" in path.read_text(encoding="utf-8")


def test_jsonl_span_exporter_redacts_names_even_when_there_is_no_error(tmp_path):
    path = tmp_path / "spans.jsonl"

    export_span(
        path,
        "private-customer-name-in-span",
        redact_errors=True,
        record_error=False,
    )

    span = read_exported_spans(path)[0]
    assert span["name"] == "[REDACTED]"
    assert "private-customer-name-in-span" not in path.read_text(encoding="utf-8")
    assert span["events"] == []
    assert span["status"]["status_code"] == "UNSET"
    assert "description" not in span["status"]


def test_jsonl_span_exporter_preserves_only_a_known_root_name(tmp_path):
    path = tmp_path / "spans.jsonl"
    export_span(path, "eval_case", redact_errors=True, record_error=False)
    assert read_exported_spans(path)[0]["name"] == "eval_case"


def test_jsonl_span_exporter_appends_spans_from_multiple_instances(tmp_path):
    path = tmp_path / "spans.jsonl"

    export_span(path, "first-span", redact_errors=False)
    export_span(path, "second-span", redact_errors=False)

    assert [span["name"] for span in read_exported_spans(path)] == [
        "first-span",
        "second-span",
    ]

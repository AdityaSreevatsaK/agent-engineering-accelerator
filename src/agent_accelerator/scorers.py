"""Deterministic checks. One scorer applies every expectation a case declares.

A case passes only if all its declared checks pass. Further checks can be added as ordinary
Inspect scorers passed to build_task; compare treats each scorer's per-case value separately.
"""

import hashlib
import hmac
import json
import re
import secrets
from typing import Any

import jsonschema
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState

from agent_accelerator.dataset import Case, ExpectedToolCall, case_from_metadata
from agent_accelerator.tool_metrics import score_metadata as tool_use_metadata

CASE_CHECKS = "case_checks"  # registered name of case_checks below


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(".").casefold()


def error_type(error: str) -> str:
    """Adapters record errors as "Type: message"; the message can carry user data, the type cannot."""
    return error.split(":", 1)[0]


def outputs_match(expected: str, actual: str) -> bool:
    try:
        return float(expected) == float(actual)
    except ValueError:
        return normalise(expected) == normalise(actual)


def _call_matches(expected: ExpectedToolCall, actual: dict[str, Any]) -> bool:
    if expected.name != actual["name"]:
        return False
    if expected.match == "exact":
        return expected.arguments == actual["arguments"]
    return all(k in actual["arguments"] and actual["arguments"][k] == v for k, v in expected.arguments.items())


def check_tool_calls(case: Case, actual: list[dict[str, Any]], show_values: bool = False) -> str | None:
    """Expected calls must appear in order. Returns a failure message, or None on success."""
    assert case.expected_tool_calls is not None
    remaining = iter(enumerate(actual))
    matched: list[int] = []
    for position, expected in enumerate(case.expected_tool_calls, start=1):
        hit = next((i for i, call in remaining if _call_matches(expected, call)), None)
        if hit is None:
            arguments = f" {expected.arguments}" if show_values else ""
            return f"expected call {position} {expected.name}({expected.match}{arguments}) not found in order"
        matched.append(hit)
    extra = len(actual) - len(matched)
    if extra and not case.allow_extra_tool_calls:
        return f"{extra} unexpected tool call(s): {[c['name'] for i, c in enumerate(actual) if i not in matched]}"
    return None


def check_trajectory(case: Case, actual: list[dict[str, Any]], show_values: bool = False) -> dict[str, str | None]:
    """Trajectory checks over the adapters' normalised calls ({"name", "arguments"}), each scored on its own.

    Tool names come from the dataset or the agent's tool list and are shown; argument values are payload
    data, so expected_tool_args names only the keys unless show_values is set.
    """
    names = [call["name"] for call in actual]
    results: dict[str, str | None] = {}
    if case.expected_tools is not None:
        missing = [t for t in dict.fromkeys(case.expected_tools) if t not in names]
        results["expected_tools"] = None if not missing else f"tool(s) never called: {missing}"
    if case.tool_order is not None:
        remaining = iter(names)
        failure = None
        for position, tool in enumerate(case.tool_order, start=1):
            if tool not in remaining:  # consumes the iterator, so later steps must come after this one
                failure = f"step {position} of {len(case.tool_order)} {tool!r} not found in order"
                break
        results["tool_order"] = failure
    if case.forbidden_tools is not None:
        called = [t for t in dict.fromkeys(case.forbidden_tools) if t in names]
        results["forbidden_tools"] = None if not called else f"forbidden tool(s) called: {called}"
    if case.max_tool_calls is not None:
        over = len(actual) > case.max_tool_calls
        results["max_tool_calls"] = f"{len(actual)} tool calls, at most {case.max_tool_calls} allowed" if over else None
    if case.expected_tool_args is not None:
        unmatched = [
            spec.tool + (f"{spec.args}" if show_values else f"(keys {sorted(spec.args)})")
            for spec in case.expected_tool_args
            if not any(
                _call_matches(ExpectedToolCall(name=spec.tool, arguments=spec.args, match="subset"), call)
                for call in actual
            )
        ]
        results["expected_tool_args"] = None if not unmatched else f"no call matching: {', '.join(unmatched)}"
    return results


def check_interrupt(expected: bool | None, interrupted: bool) -> str | None:
    """An interrupt is a terminal outcome: it passes only when the case sets expect_interrupt true."""
    if expected and not interrupted:
        return "expected an interrupt"
    if interrupted and not expected:
        return "unexpected interrupt"
    return None


def run_checks(case: Case, completion: str, metadata: dict[str, Any], show_values: bool) -> dict[str, str | None]:
    """Returns {check name: failure message or None}. show_values=False keeps payloads out of messages."""

    def shown(value: str) -> str:
        return repr(value) if show_values else "<redacted>"

    results: dict[str, str | None] = {}
    if metadata.get("agent_error"):
        error = metadata["agent_error"]
        results["agent_error"] = error if show_values else error_type(error)
    interrupted = bool(metadata.get("interrupted"))
    if case.expect_interrupt is not None or interrupted:
        results["expect_interrupt"] = check_interrupt(case.expect_interrupt, interrupted)
    if case.expected_output is not None:
        ok = outputs_match(case.expected_output, completion)
        results["expected_output"] = None if ok else f"expected {shown(case.expected_output)}, got {shown(completion)}"
    if case.output_contains is not None:
        missing = [s for s in case.output_contains if s.casefold() not in completion.casefold()]
        results["output_contains"] = None if not missing else f"output missing {len(missing)} required substring(s)"
    if case.output_not_contains is not None:
        found = [s for s in case.output_not_contains if s.casefold() in completion.casefold()]
        # The forbidden strings come from the dataset, but listing them shows what the output said.
        listed = f": {found!r}" if show_values else ""
        results["output_not_contains"] = (
            None if not found else f"output contains {len(found)} forbidden substring(s){listed}"
        )
    if case.expected_json_schema is not None:
        try:
            jsonschema.validate(json.loads(completion), case.expected_json_schema)
            results["json_schema"] = None
        except json.JSONDecodeError:
            results["json_schema"] = "output is not valid JSON"
        except jsonschema.ValidationError as exc:
            # absolute_path and message are built from the output; schema_path and validator come from the schema.
            schema_at = "/".join(map(str, exc.schema_path)) or "<root>"
            if show_values:
                output_at = "/".join(map(str, exc.absolute_path)) or "<root>"
                results["json_schema"] = (
                    f"schema violation at {output_at} (schema {schema_at}): {exc.validator}: {exc.message}"
                )
            else:
                results["json_schema"] = f"schema violation at schema {schema_at}: {exc.validator}"
    if case.expected_tool_calls is not None:
        results["tool_calls"] = check_tool_calls(case, metadata.get("tool_calls", []), show_values)
    results.update(check_trajectory(case, metadata.get("tool_calls", []), show_values))
    return results


def output_digest(key: bytes, completion: str) -> str:
    """HMAC-SHA256 of the output, truncated to 64 bits: enough to tell outputs apart within one run."""
    return hmac.new(key, completion.encode(), hashlib.sha256).hexdigest()[:16]


@scorer(metrics=[accuracy()])
def case_checks(show_values: bool = False):
    # Keyed per scorer instance (one per run) and never stored: equal outputs within a run share a digest, but a
    # digest cannot be matched across runs or reversed by hashing guesses, even for short outputs.
    digest_key = secrets.token_bytes(32)

    async def score(state: TaskState, target: Target) -> Score:
        case = case_from_metadata(state.metadata)
        results = run_checks(case, state.output.completion, state.metadata, show_values)
        failures = [f"{name}: {msg}" for name, msg in results.items() if msg]
        return Score(
            value=INCORRECT if failures else CORRECT,
            explanation="; ".join(failures) if failures else "all checks passed",
            # Score metadata survives the scrub, so the call count reaches reports; None if the adapter recorded none.
            metadata={
                "checks": {name: msg is None for name, msg in results.items()},
                "tool_call_count": len(calls) if (calls := state.metadata.get("tool_calls")) is not None else None,
                "output_digest": output_digest(digest_key, state.output.completion),
                **tool_use_metadata(case, calls, state.metadata.get("tool_errors")),
            },
        )

    return score

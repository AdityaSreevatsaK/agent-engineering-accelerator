# AEA technical/security audit: trace-exporter payload minimisation

**Date:** 12 November 2026  
**Classification:** Newly authored production-oriented hardening, **NOT** a transcription of original AEA source.  
**Target:** `reconstruction/wip-checkpoint-2026-10-30`, not `master`.

## Confirmed finding

**Priority: High for use with confidential client workloads.** `src/agent_accelerator/tracing.py` previously serialised all OpenTelemetry span attributes to `traces.jsonl`. In default redacted mode, its exporter only replaced `exception.message`, `exception.stacktrace` and status descriptions. It relied on Strands and OpenInference environment flags for sensitive data produced by their instrumentation. Those flags do not control arbitrary custom spans created by agent/tool code, and nothing in the exporter prevented custom attributes (e.g. `custom.request_input`, `gen_ai.input.messages`, `llm.prompt`) or custom event payloads from being persisted. This is a **code-level data-leak path**, not proof that a real customer's data has already leaked.

## Narrow change

For default, non-capture tracing only:

- Retain the six span attributes required by the existing AEA trace summary: case ID, epoch, operation name, OpenInference span kind and the two tool-name keys.
- Strip other span attributes, resource/scope metadata, links and non-exception event payloads/names.
- Retain `exception.type`, redact exception message/stacktrace and span status description.
- Preserve span identity, timestamps and status so the existing report's model/tool counts and durations continue to work.
- Keep the explicitly user-selected `--capture-content` mode unchanged.
- Cover custom prompt/response attributes, nonexception events, existing original tracing behaviour and report summaries with synthetic offline tests on Windows/Linux Python 3.11/3.12.

The prior byte-level reconstructed `tracing.py` is preserved in the integration branch's commit history at `80b7476d60b0813eb3c7e790e70f4134aae7666e`, Git blob `e253d440bb1132a087861586da606462277bf768`. This post-audit change must never be counted as historical source fidelity.

## Residual boundaries

**This is not anonymisation.** Span names, case IDs, tool names, timing and trace IDs remain, and any of these names may themselves contain identifiers if the application embeds them. Tool/agent imports execute trusted user code outside any sandbox. Redacted Inspect scores and exported reports need separate privacy review; captured logs intentionally retain payloads. Use synthetic identifiers in shared CI and review traces before sharing.

## Other release blockers observed

- `aea check --update-baseline` validates the target before running the agent and later deletes/replaces it without rechecking. Concurrent filesystem edits can still create a time-of-check/time-of-use data-loss race; this was separately acknowledged in `reconstruction_audits/2026-11-06_part42_baseline_freeze_safety.md`. A transactional baseline design is still pending.
- The original lockfile, historical baseline artifacts, original capture fixtures and sign-off remain unavailable. Modern green CI does **not** imply exact historical reproduction.
- Real cloud agents, repeatability, adopted client workflows, cost/latency quality gates and production security review remain outside the verified offline test boundary.

**Decision:** This privacy hardening reduces one practical exposure but cannot by itself authorise production release or a merge into `master`.

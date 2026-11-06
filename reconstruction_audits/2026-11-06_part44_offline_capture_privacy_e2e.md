# AEA Reconstruction Part 44: Real offline privacy and capture-content verification

**Date:** 6 November 2026  
**Target branch:** `reconstruction/wip-checkpoint-2026-10-30`  
**Classification:** Newly written validation; not historical v2.2.0 source transcription.

## Motivation

The previously successful original-path and offline starter unit/E2E suites verify the `scrub` implementation in isolation, but the live CLI path had not been checked for accidental persistence of user-provided prompt content. End-to-end redaction is critical for internal reuse because Inspect logs, OpenTelemetry traces and Markdown reports can be retained or shared by delivery teams.

## Scenario

The existing E2E smoke uses the real AEA CLI and the deterministic Strands starter agent in a disposable temporary directory, on both Windows and Ubuntu and Python 3.11/3.12. We now append a unique, harmless sentinel to the offline starter's existing no-tool prompt. We retain the original five-case dataset structure and outcomes; the string exists **only inside the temporary test input**, not in any original or synthetic committed fixture.

The test verifies:
- Successful first baseline freeze (5/5), repeated check (5/5) and normal reports are still produced.
- The sentinel is **absent from all generated on-disk files** within the redacted baseline and both normal run directories: native Inspect JSON, traces, Markdown and any additional generated files.
- A deliberately regressed third normal-mode check (4/5) also does not leak the sentinel into its run directory.
- An additional real `aea run --capture-content` preserves the sentinel in its explicit sensitive Inspect JSON log, proving the opt-in actually works rather than merely hiding all data.
- Capturing a separate run does not contaminate the previously frozen redacted baseline.

## Security boundary and caveats

All model/tool execution remains local using the deterministic offline `build_offline_agent`; no cloud model or provider calls. This is a focused **integration privacy assertion**, not a formal proof that all sensitive content is scrubbed under all frameworks, custom scorers or exception formats. The sentinel is intentionally non-secret and unique; it is not client data. Capture-content logs are generated under `TemporaryDirectory`, are never committed to GitHub, and are deleted when the scenario ends.

This change only modifies the new `reconstruction_tools/verify_offline_template_e2e.py` verification script, not the historical original CLI or any original test file. The 60 historic fixture/config-dependent tests stay deferred.

**Acceptance:** merge into the reconstruction review branch only after all 10 GitHub Actions workflows/37 jobs pass, followed by all 8 reconstruction-branch checks. Do not merge the project into `master` or claim full original-source fidelity.

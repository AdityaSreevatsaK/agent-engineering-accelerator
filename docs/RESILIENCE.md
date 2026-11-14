# AEA: adversarial resilience and baseline-integrity validation

**Scope:** Repeatable synthetic, deterministic correctness tests on Windows and Linux. The tests simulate failures; they do not exercise live cloud rate limits, networks, remote providers or confidential client data.

## Scenarios and expected result

| Risk / injected fault | Reproducible assertion | File/contract |
| --- | --- | --- |
| Two simultaneous AEA writers to the same approved baseline | Hold one writer *inside the real staging copy* while a second writer attempts to publish. Second fails on the exclusive lock, existing baseline stays readable, first writer completes and retains the previous snapshot | `test_resilience_adversarial.py::test_genuinely_overlapping_writers_are_serialised_and_reader_remains_safe` |
| Invalid log in a candidate run | Feed truncated text, a JSON array and structurally invalid Inspect-like documents to baseline publication. Refuse to replace previous content; release lock and do not leave staging or backup folders | `test_corrupted_candidate_log_does_not_replace_valid_baseline` |
| I/O failure *after* a partial write | Inject an exception after creating a synthetic partial staged file. The prior baseline and its report remain byte-identical, with no partial payload left in staging | `test_partial_stage_copy_failure_does_not_leave_payload_or_mutate_prior` |
| Invalid input to the public `aea compare` command | Verify a usage/run error, no modification to a pre-existing output report and no deletion of malformed source input | `test_corrupted_compare_input_exits_with_error_without_overwriting_report` |
| Multiple successive baseline updates | Both earlier snapshots remain discoverable in a read-only backup inventory; none is silently purged | `test_multiple_updates_retain_each_prior_baseline_instead_of_purging` |

Additional pre-existing tests cover symlink traversal, pre-existing unrelated files, lock files, protected permissions, staged publish rollback, malicious score payload redaction and synthetic adapter quality regressions.

Run all non-slow cases from the repository root, with the pinned environment:

```sh
uv run --locked python scripts/run_checks.py
```

The complete CI matrix runs on Windows/Linux with Python 3.11/3.12. Failures prevent a PR merge; release checks also run the slow CLI and provider-free integration suite. No cloud API keys or live model calls are needed.

## What the evidence does and does not establish

- **Can establish:** Deterministic handling of the enumerated injected failure points and preservation of approved data under these specific interleavings, on the tested runtimes.
- **Cannot establish:** Data durability under actual power loss, all filesystem semantics, every possible concurrent writer, uncooperative external processes, Windows enterprise ACL policies, recovery of a lost operator-controlled lock, provider rate limiting, long-run memory stability or client security approval.

The exclusive lock coordinates **AEA writers only**. It does not control other programs modifying the same directories. Existing baseline activation briefly renames directories; concurrently reading during that exact rename window may fail, so do not advertise zero-downtime snapshots. Previous backups are intentionally retained until an approved retention policy exists.

## Future reliability expansion

1. In an approved environment, test genuine disk quota exhaustion and abrupt process termination at several checkpoint boundaries using disposable storage, then verify restart/recovery guidance.
2. Measure long-duration repeated evaluations and memory/storage growth on representative approved workloads. Keep this separate from the short benchmark in [BENCHMARKING.md](BENCHMARKING.md).
3. Test real provider failures, transient network interruptions and rate limiting only with explicit service approvals and credentials outside CI.
4. When other engineers become available, capture actual onboarding issues and failure interpretation in [the pilot evidence worksheet](PILOT_EVIDENCE_TEMPLATE.md).

**Decision boundary:** Passing these tests increases confidence for **controlled synthetic pilots**; formal security approval and independent adoption evidence remain required for customer production use.

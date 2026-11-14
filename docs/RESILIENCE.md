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
| Existing baseline cannot be moved into backup | Inject a failed rename; the approved baseline stays byte-identical and the newly created empty backup container is removed without touching unexpected contents | `test_baseline_transaction.py::test_failed_prior_snapshot_move_preserves_original_and_cleans_empty_backup` |
| Process terminates abruptly after backing up the prior baseline but before activation | An isolated child exits without cleanup; the original log is recoverable in the retained backup and an untouched lock blocks automatic retries. The active baseline is **temporarily missing**, requiring operator recovery | `test_baseline_crash_safety.py::test_abrupt_exit_preserves_previous_baseline_and_blocks_automatic_reuse` |

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

1. Extend abrupt-stop coverage to additional checkpoints, and test real disk quota exhaustion and host/power loss in an approved disposable environment. The current test covers **one controlled interpreter-exit boundary**, not data durability across power failure.
2. Measure long-duration repeated evaluations and memory/storage growth on representative approved workloads. Keep this separate from the short benchmark in [BENCHMARKING.md](BENCHMARKING.md).
3. Test real provider failures, transient network interruptions and rate limiting only with explicit service approvals and credentials outside CI.
4. When other engineers become available, capture actual onboarding issues and failure interpretation in [the pilot evidence worksheet](PILOT_EVIDENCE_TEMPLATE.md).

**Decision boundary:** Passing these tests increases confidence for **controlled synthetic pilots**; formal security approval and independent adoption evidence remain required for customer production use.


## Recovery when a process stops during baseline replacement

The subprocess fault test deliberately leaves a missing active baseline, a retained `.aea-update.lock`, and a prior snapshot under `.aea-backup-*/previous`. This is a **recoverable, operator-managed state**, not an automatic rollback or a zero-downtime guarantee.

1. Stop further evaluations against this baseline and establish that **no AEA writer** is still running. Do not assume the lock is stale just because an earlier command failed.
2. Inspect the target, the lock, and previous snapshot directories without deleting or overwriting any path. `aea backups PATH_TO_BASELINE` lists retained previous versions read-only even if the active baseline is missing.
3. Verify the intended prior snapshot's evaluation log, report and identity. If the target has reappeared, treat it as an ownership conflict and stop rather than overwriting it.
4. Only an authorised operator should restore the selected snapshot using a platform-appropriate, non-destructive process, verifying that it preserves existing contents. Preserve the original retained backup for audit until recovery is verified. Review Windows ACLs where applicable.
5. After verifying that no writer exists and the baseline is readable, explicitly review the retained lock and any orphaned staging directory. Never remove or reuse either automatically.

The tool does not determine whether an externally retained lock is safe to remove, automatically restore snapshots, or promise an atomic cross-process reader view.

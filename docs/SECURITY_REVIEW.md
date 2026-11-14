# AEA security review evidence

**Status: engineering self-assessment, not independent security sign-off.**

## Threat boundaries

| Risk | Current evidence | Remaining action |
| --- | --- | --- |
| Prompts, outputs and tool arguments in Inspect logs | The runtime scrubs sample input, target, messages, events, attachments and non-approved scorer metadata | Verify the end-to-end no-content contract using a synthetic sentinel on both adapters |
| Sensitive exception text or custom tracing attributes | The default exporter minimises custom span attributes, sanitises exception messages and removes arbitrary non-root span names | Trace identifiers, case IDs and tool names are not anonymised |
| Explicit `--capture-content` logs | Intentionally persists raw model input/output and tool content | Approved access control, storage location and retention process required before customer use |
| Agent factories and custom scorers | Trusted imported Python executes in the user's process | Run only reviewed source within approved environments |
| Secrets and cloud-provider calls | Offline examples use local deterministic doubles, and CI clears common provider credentials | Confirm no unexpected account access or billable calls during planned pilots |
| HTML reports | Output escapes raw HTML; fresh-wheel export is tested | Review output access and distribution pathways |
| Baseline replacement and retention | Cooperative update lock, revalidation, staged deployment, backups, rollback tests and refusal of obvious unredacted sample payloads before replacement | Review the new POSIX owner-only snapshot modes and non-destructive `aea backups` inventory; approve Windows ACLs, encryption, retention and removal |
| Dependencies | `uv.lock` committed, locked installation checked on Windows/Linux | Run a dated vulnerability/advisory and licence review using the [dependency self-assessment](DEPENDENCY_SECURITY_REVIEW.md), followed by authorised sign-off |
| Operational failures | Tests cover controlled regressions, error statuses and conformance | Validate network failures and rate limits against approved providers |

## Runnable privacy contract

```sh
uv run --locked python scripts/check_privacy_e2e.py
```

The check puts a synthetic private marker in a temporary JSONL dataset, invokes
the public CLI with **Strands and LangGraph**, and fails if that marker appears
in default report, log, trace or CLI output. It verifies that explicit capture
retains the marker and removes the temporary captured files when finished.
This verifies the tested paths only; it does not guarantee anonymisation.

## Independent decisions still required

- [ ] Review sensitive identifiers in case IDs, span names, tool names and paths
- [ ] Approve classification and retention for logs, traces and backup folders
- [ ] Review secrets and provider permissions for any live pilot
- [ ] Run dependency security and licence scans under MathCo policy
- [ ] Approve synthetic demonstration and pilot datasets and access control
- [ ] Obtain explicit security sign-off before confidential customer workloads

Passing CI and this assessment are not security certification.

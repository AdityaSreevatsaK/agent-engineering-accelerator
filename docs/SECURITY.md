# Security and data handling

AEA runs locally and executes user-supplied Python agent factories, input/output mappings and scorers. Treat these as trusted code. Do not run untrusted modules or datasets with elevated permissions.

## Data protection

- **Default runs:** Inspect log prompts, outputs and tool-message payloads are redacted. Arbitrary non-numeric custom-scorer values are replaced with a failing category to prevent output text leaking via score values. Standard Inspect categories and numeric grades are retained. The trace exporter also removes arbitrary custom span attributes, non-exception event payloads and all non-root span names. Its fixed `eval_case` root name is preserved for trace grouping. Tool names and case IDs remain visible and require safe naming.
- **Remaining identifiers:** Case IDs, tool names, model identifiers, relative paths, timings and numerical metrics may still identify an individual or client; non-root span names are redacted in default trace exports. Explicit capture retains full span names.
- **Explicit capture:** `--capture-content` stores raw evaluation content. Keep such data in an approved restricted location, apply your retention policy and never commit it.
- **Export:** Markdown, HTML and PDF reports are files you control. Inspect their content and permissions before sharing.
- **Credentials:** Configure provider credentials through the hosting environment or approved secrets management, never in code or datasets.
- **Cloud costs:** Local sample agents use deterministic doubles. Live providers and model judges can incur charges if configured.

## Deployment readiness

Before using customer data, verify data classification, access control, retention, supply-chain dependencies and the intended model providers. Offline CI does not constitute production security certification.

## Known limitations

Baseline updates use an exclusive local lock, a validated staging directory and a retained prior-version backup. They do not guarantee coordination with external processes that ignore the lock. A lock left after a crash must be investigated and cleared manually. Prior backups are not automatically purged: run `aea backups PATH` to list retained versions without modifying them, then follow an approved retention policy. New snapshots are set to owner-only modes on POSIX (folders 0700, files 0600) before activation, without altering source run files. Windows needs an explicit NTFS ACL and storage-location review; POSIX modes alone do not guarantee confidentiality on all shared filesystems. Baseline updates reject logs explicitly marked as captured or containing sample input, target, messages, output text, events, attachments or store content. This is a focused safety check, not proof that all metadata or custom score fields are anonymous. Default trace redaction minimises fields but is not a comprehensive anonymisation boundary.

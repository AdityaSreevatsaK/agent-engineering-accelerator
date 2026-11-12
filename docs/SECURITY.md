# Security and data handling

AEA runs locally and executes user-supplied Python agent factories, input/output mappings and scorers. Treat these as trusted code. Do not run untrusted modules or datasets with elevated permissions.

## Data protection

- **Default runs:** Inspect log prompts, outputs and tool-message payloads are redacted. The trace exporter also removes arbitrary custom span attributes and non-exception event payloads.
- **Remaining identifiers:** Case IDs, tool names, span names, model identifiers, relative paths, timings and numerical metrics may still identify an individual or client.
- **Explicit capture:** `--capture-content` stores raw evaluation content. Keep such data in an approved restricted location, apply your retention policy and never commit it.
- **Export:** Markdown, HTML and PDF reports are files you control. Inspect their content and permissions before sharing.
- **Credentials:** Configure provider credentials through the hosting environment or approved secrets management, never in code or datasets.
- **Cloud costs:** Local sample agents use deterministic doubles. Live providers and model judges can incur charges if configured.

## Deployment readiness

Before using customer data, verify data classification, access control, retention, supply-chain dependencies and the intended model providers. Offline CI does not constitute production security certification.

## Known limitations

Baseline updates use an exclusive local lock, a validated staging directory and a retained prior-version backup. They do not guarantee coordination with external processes that ignore the lock. A lock left after a crash must be investigated and cleared manually. Prior backups are not automatically purged; secure or delete them according to your retention policy. Default trace redaction minimises fields but is not a comprehensive anonymisation boundary.

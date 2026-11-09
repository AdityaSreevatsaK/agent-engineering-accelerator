# Acceptance and review video fidelity pass: 9 November 2026

## Scope

This audit expands two already-merged **provisional** documentation drafts, using the user-supplied recordings `docs-acceptance.md.webm` (approximately 26 seconds) and `docs-review.md.webm` (approximately 20 seconds). Neither original historical path (`docs/acceptance.md` or `docs/review.md`) has been restored by this PR.

### Newly checked frame anchors

- `docs/review.md`, editor **lines 98–111**: retention statement, six-row artefact table, manual deletion, ignored run directories, non-ignored baselines. The previous draft stated the general retention policy but omitted the table.
- `docs/review.md`, editor **lines 113–126**: trust boundaries for dynamically imported agents, scorers and maps; explicit TOML configuration and precedence; unsandboxed scorer access to pre-scrub content; datasets as trusted instructions to agents; process-wide tracing environment variables.
- `docs/review.md`, editor **lines 128–142**: residual risks and link to README known limitations. Earlier draft captured the core risk types; the additional details above are in sections 4 and 5.
- `docs/acceptance.md`, editor **lines 137–147**: six-row explicitly not-met/deferred table, now represented with separate recorded mitigation/plan entries.
- `docs/acceptance.md`, editor **lines 148–154**: historical version-specific summary stating the 2.0.0 verdict was not rerun for 2.2.0.

### Validation boundaries

The revised drafts are Markdown notes with evidence-backed **semantic reconstruction**. The original documents' exact punctuation, table formatting, sequence, line counts and complete unit-test coverage matrix have **not** been recovered. New commentary and the “provisional” warnings are deliberately not part of historical source.

Do not:
1. Copy the drafts into original `docs/` paths and claim they are exact source.
2. Treat 2026 historical developer acceptance statements as new verification of the current reconstructed branch.
3. Count these drafts in the original 117-file manifest or raise the historical-path inventory floor because of them.

The historical release/CI readiness review remains separate. The current reconstruction integration branch and `master` are unchanged except for this evidence-preservation PR targeting the former.

# AEA reconstruction release-evidence audit — 9 November 2026

## Decision

**Do not merge the entire reconstruction into master yet.** The historical source inventory contains 117 paths, of which 97 are currently present. This measures path recovery, not byte-identical source evidence or final acceptance.

This change adds a dependency-free, offline reporting tool:

- python -m reconstruction_tools.audit_release_evidence --format markdown
- python -m reconstruction_tools.audit_release_evidence --format json

The flag --require-release-ready is deliberately fail-closed. Green reconstructed CI or synthetic placeholders do not constitute original-video fidelity certification, historical fixture recovery or human release sign-off.

## Original path inventory (before this PR)

| Category | Present | Expected | Missing |
| --- | ---: | ---: | ---: |
| CI | 0 | 1 | 1 |
| Baselines | 0 | 14 | 14 |
| Documentation | 0 | 2 | 2 |
| Examples | 31 | 31 | 0 |
| Scripts | 1 | 1 | 0 |
| Source | 23 | 23 | 0 |
| Tests | 37 | 39 | 2 |
| Root | 5 | 6 | 1 |
| **Total** | **97** | **117** | **20** |

The original uv.lock, both historical calculator capture fixtures, fourteen historical baseline artefacts, two original documentation files and original CI workflow path remain absent. The user already confirmed that the two original calculator captures cannot be supplied; do not request them again or fabricate historical originals.

The historical GitHub CI file is preserved as an archived recording-derived candidate under reconstruction_drafts/original_github_workflows_ci.yml.txt. Its previous attempt at activation failed without uv.lock. The original acceptance and review documents are preserved as provisional drafts, not certified originals. The historical root README.md remains a title-only stub; do not silently rewrite this historical file.

## Verified capabilities are separate from source authenticity

- The existing reconstruction suite has tested source and substantial offline functionality on Windows/Ubuntu with Python 3.11/3.12.
- PR #74 passed 11/11 workflow runs. Its new disposable-baseline checks verified calculator 10/10, triage 12/12 and expense 12/12 healthy runs; planted regressions affected two, two and three cases respectively.
- The post-merge integrity workflow for PR #74 passed 8/8 jobs.
- These checks use generated temporary logs and cannot authenticate any original historical baseline.
- The new tool only inspects tracked paths and safe local prerequisites, not baseline payloads, screenshots, remote CI job logs or production credentials.

## Remaining release gates

1. Resolve outstanding uncertain video transcriptions, preserving original evidence separately from functional adaptations.
2. Recover or formally waive missing historical files with explicit approval, not invented lookalikes.
3. Review privacy, retention and provenance before storing any historical captured logs and traces.
4. Execute historical locked CI with approved inputs, or document an explicitly approved replacement test plan covering slow, integration and release tests.
5. Complete operator documentation, security review, sign-off and final release acceptance.

No new artefact in this PR counts as one of the 117 historical files. Target the reconstruction branch; keep master unchanged.

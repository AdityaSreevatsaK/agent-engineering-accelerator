# AEA 2.2.0: technical release-candidate checklist

**Prepared:** 14 November 2026  
**Source:** `dev` after [PR #119](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/119) (merged SHA `86707008aa859bedcf2e94e22aca66c79bbe6b56`); the expanded technical checks are in [PR #120](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/120). Pin the final integrated `dev` SHA again after merging.  
**Version declared:** `2.2.0` in `pyproject.toml`.  
**Release state:** **Technical preparation only.** No promotion to `master`, release tag, package publication, confidential-data approval or independent team adoption is authorised by this checklist.

## Technical gates and source evidence

| Gate | Reproducible command or evidence | Status |
| --- | --- | --- |
| Four OS/Python combinations | Windows and Ubuntu, Python 3.11/3.12, `uv lock --check`, static checks, complete non-slow unit inventory and local smoke | Verified on [PR #119 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43590375757) |
| Non-slow unit tests | `uv run --locked python scripts/run_checks.py` | **2,646 passed** in Ubuntu Python 3.11 PR #119 check; test selection and count depend on the precise commit |
| Non-slow LangGraph conformance | `uv run --locked python -m pytest -q -m "not slow" tests/conformance` | **13 passed**, with the one marked-slow case checked separately |
| CLI subprocess integration and slow conformance | `uv run --locked python scripts/run_checks.py --slow` | [PR #120 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43591507776) passed **74 marked-slow cases** across all unit modules and conformance (the 2,659 non-slow cases were selected in the other lanes) |
| Synthetic runtime and fault-detection evidence | `uv run --locked python -m scripts.benchmark_agent_evaluations --repeats 2 --output-dir NEW_DIR` | Actual per-run CLI time and controlled defect detection; **not** developer productivity or real model-provider throughput; review CI result and summary files before citing |
| Two standalone agent integrations | `uv run --locked python scripts/validate_independent_integrations.py --repeats 1` | Strands equipment and LangGraph supplier apps each have 12 synthetic reference cases, passing good/bad regression tests |
| Synthetic redaction checks | `uv run --locked python scripts/check_privacy_e2e.py` | Both adapters checked; does not establish anonymisation of all metadata |
| Reproducible synthetic project rehearsal | `uv run --locked python scripts/pilot_rehearsal.py --output-dir <new-directory> --repeats 1` | Redacted baseline, unchanged comparison, deliberate regression and baseline integrity |
| Fresh isolated wheel install | `uv build --wheel` followed by `uv run --locked python scripts/check_distribution.py` | Installs a wheel in a disposable environment and checks import, metadata, templates, CLI commands, escaped HTML and read-only backup discovery |
| Adversarial baseline/CLI safety | `uv run --locked python scripts/run_checks.py` | Concurrent publishers, corrupt logs, partial copy interruption and backup retention must preserve operator data; see [resilience matrix](RESILIENCE.md) |
| Observational public advisory scan | [PR #124 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43627751480), `scripts/audit_public_advisories.py` | 116 packages scanned, 0 known findings in the exported runtime selection; remaining variants and licences unverified, security sign-off pending |
| Packaging and branch integrity | Current `dev` CI plus `master` still unchanged | Must be independently rechecked after the final merge |

All automated case inputs in these gates are synthetic. Neither a passing gate nor a signed report indicates customer production security approval. No billable model-provider calls are permitted in CI.

## Failure policy and evidence interpretation

- **Do not merge if any of the six CI jobs fails, is cancelled, is skipped unexpectedly or has not completed.**
- Do not claim that the unavailable original calculator reference files were restored. The test runner generates separate disposable synthetic logs, including two intentionally introduced score failures; it refuses to overwrite existing files and checks their digests before cleanup.
- `aea run` can return exit 0 for a completed evaluation with failing cases; `aea check` and `aea compare` enforce the configured regression thresholds. Keep tests for both behaviours.
- Slow testing must cover **all** marked-slow unit cases, including token price CLI checks and expense, helpdesk, policy RAG and triage end-to-end checks, plus the LangGraph CLI conformance case. Check the pytest selected/deselected summary in the release job.
- A green generated fixture can validate the current CLI contract, not independently certify the correctness of unknown prior run artefacts.

## New onboarding/operational readiness acceptance (pending PR CI)

- Run `aea doctor` on both synthetic integrations from their application directories before first evaluation.
- Confirm the installed **base wheel** supports `aea doctor` without installing a framework extra; verify it does not create evaluation runs and that missing modules return exit 2.
- Verify LangGraph mapper advisory text, config/CLI precedence and invalid JSONL diagnostics.
- Review the [onboarding](ONBOARDING.md), [operational recovery](OPERATIONAL_READINESS.md) and [adoption evidence](ADOPTION_EVIDENCE.md) guidance. These documents do not represent external approval.
- After final PR merge, update the evidence reference using the actual integrated `dev` SHA and 6/6 CI result. Do not treat pending CI as passed.

## Outstanding sign-offs for a real release

| Owner / gate | Requirement | Current disposition |
| --- | --- | --- |
| Security and data governance | Customer data classification; default trace and log identifiers; output file access; approved redaction, capture and deletion | **Not approved** |
| Operations | Backup retention, encrypted storage, manual stale-lock handling and Windows NTFS ACLs | **Unapproved policy** |
| Dependency/supply chain | Licence and vulnerability review using approved sources; verify wheel contents and locked dependencies | Installed-wheel verification passed in PR #120 CI; formal review outstanding |
| Framework compatibility | Explicitly approved real Strands and LangGraph integrations, including provider errors, rate limits and actual usage | Local deterministic doubles only |
| Adoption | Independent engineering work by two delivery teams and documented measurable outcomes | **Not completed**; [Issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) |
| Release ownership | Review release notes, approve `master` change, choose version/tag and distribution targets | **Approval not requested** |

## Controlled candidate preparation

1. Confirm the latest `dev` commit and all open PRs/branches. Pin a single immutable SHA for the candidate.
2. Confirm **6/6 green on that same SHA**, including the complete slow-test gate and both synthetic integration examples. Record the actual CI link and individual test totals.
3. Inspect `CHANGELOG.md`, `docs/RELEASE_READINESS.md`, `AGENTS.md` and the package metadata; do not describe earlier missing reference inputs as independently restored.
4. Generate one wheel using the locked dependency environment; run the isolated wheel check and inspect the package for private content, cached runs and unexpected files.
5. Prepare a release note and list outstanding approvals; save internal-only evidence outside this public repository.
6. **Stop at a technically validated candidate on `dev`.** Promotion to `master`, creation of a tag, uploading packages and production claims all require explicit release-owner approval and the relevant security/pilot sign-offs.

**Current decision:** Continue controlled local/synthetic evaluation. This document does not authorise general availability or production customer data.

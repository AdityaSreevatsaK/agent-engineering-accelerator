# AEA 2.2.0: operational controls and recovery playbook

**Status:** Engineering guidance for approved local, synthetic-data rehearsals only. This is not an approved information-security policy or a customer production procedure.

## Before the first run

| Gate | Required operator decision | Current posture |
| --- | --- | --- |
| Input classification | Use synthetic cases or obtain documented approval for the precise data class | Only synthetic data is approved for self-contained examples |
| Imported code | Review `module:function` agents, scorers and mappers; Python imports and factories may execute arbitrary code | AEA is not a sandbox |
| Content capture | Leave `--capture-content` **off** unless separately approved | Default redaction reduces content but leaves some identifiers |
| Output storage | Select a dedicated, access-controlled local location; identify an owner | Local paths and traces may reveal identifying metadata |
| Provider usage | Pin approved credentials, rate limits, budgets and execution boundaries outside ordinary CI | Current CI must remain offline and non-billable |
| Retention | Decide authorised retention/deletion, backup ownership and encrypted storage | No automatic backup purge policy is approved |
| Windows controls | Review native NTFS ACLs and user profiles with operations/security | POSIX `chmod` coverage is not a Windows ACL audit |

**Stop and escalate** if raw customer prompts, secrets, tokens, unapproved identifiers or unexpected provider traffic appear in logs or tracing. Preserve incident evidence only under an approved policy. Do not copy sensitive artefacts into this public repository.

## Healthy baseline lifecycle

1. Select the baseline directory outside `--runs-dir`; validate it using the normal `aea check` workflow.
2. Freeze a redacted reference with explicit `--update-baseline`. Never combine baseline publishing with `--capture-content`.
3. Compare unchanged and deliberately defective agents; check expected CLI exits and baseline fingerprints.
4. Record snapshot owners, where encrypted evidence is kept, and how long retained backups may exist.
5. Inspect backup versions read-only with `aea backups PATH_TO_BASELINE`. **No automatic removal or restoration is implemented.**

## AEA stopped unexpectedly: manual recovery

The baseline update uses a cooperative lock, staging directory and retained prior snapshot. An abrupt interpreter stop **between backing up the old baseline and activating the new one** can leave the active baseline path absent, the old version under `.<baseline>.aea-backup-*/previous`, an orphaned stage, and a retained `.<baseline>.aea-update.lock`.

1. Prevent further writes and establish that no AEA writer or external process is still using the target. A lock being old is insufficient proof.
2. Inspect the current baseline, its parent directory and its named backups **without mutating files**. Use the read-only backup inventory.
3. Verify a candidate backup's real Inspect log, report, expected identity and fingerprints. Preserve every pre-existing operator file.
4. If the active baseline is missing, ask an authorised operator to select an approved recovery method appropriate to that filesystem and access-control policy. Never blindly rename into an occupied path.
5. Check access permissions and the restored baseline's contents before any further evaluation. Only after establishing no active writer should an authorised operator assess retained locks/stages for removal.
6. Record what was retained or restored and document the incident; do not silently purge backups.

**Scope limits:** Tests cover one controlled `os._exit` boundary and deterministic error injections. They do not establish resilience against power failure, actual disk exhaustion, non-cooperating writers, external filesystem modification, live-provider outages or a zero-downtime reader view.

## Owner decisions still open

- [ ] Customer-data classification, access and log-identifier handling
- [ ] Encryption, storage and retention for run logs, traces and backups
- [ ] Windows ACL and shared-filesystem review
- [ ] Authorised stale-lock diagnosis and manual recovery responsibility
- [ ] Approved live-provider test plan and service quotas
- [ ] Independent dependency licence/security sign-off
- [ ] Release-owner approval to promote `dev` to `master`

These are blocking approval gates, not feature-work items that can be closed using green CI alone. See [security review](SECURITY_REVIEW.md), [resilience tests](RESILIENCE.md) and [release checklist](RELEASE_CANDIDATE_CHECKLIST.md).

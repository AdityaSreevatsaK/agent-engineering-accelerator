# AEA security approval handover (reviewer worksheet)

**State:** Engineering evidence only. No independent approver has reviewed or signed this.
**Source of truth:** `dev`, `uv.lock`, [issue #125](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/125) and [release gate #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111).
Do not publish real project, user or customer data in issues or CI artefacts.

## 1. Package and public advisory review

- **Initial** full-lock audit: 128 package records, including 127 registry versions, found three public Soup Sieve 2.10 advisories. The vulnerable alternative applied only to Python 3.11.0-3.11.4.
- **Remediated candidate**: minimum Python **3.11.5**, regenerated uv lock with **127 records (126 registry versions)** and **Soup Sieve 4.1 only**. See [CVE remediation](SOUPSIEVE_SECURITY_REMEDIATION.md).
- Four CI environments (Windows/Linux, Python 3.11/3.12) each run a pinned public advisory scan. The individual runtime selections were **116/127 on Linux** and **117/127 on Windows**, with **zero known advisory findings reported** on 15 November 2026. Runtime scans exclude development dependencies and unselected Python/OS alternatives.
- New `scripts/audit_all_locked_variants.py` checks **all 126 currently locked registry versions** without installing them. It separates packages with multiple locked versions into non-conflicting requirements batches, includes development-only and other-platform packages, and verifies every auditor-returned identity against the lock. CI retains `aea-complete-lock-advisories` (JSON and Markdown) for **14 days**.
- **Auditor limitation:** public advisory data cannot rule out unpublished vulnerabilities, compromised packages or malicious behaviour. Successful scanning is not certification.
- **Reviewer action:** inspect actual dated CI artefacts and any reported advisories; document accepted findings and sources in an approved restricted system. Re-run scans before a release decision.

## 2. Why earlier runtime scans missed entries

**Earlier evidence only:** names omitted by the runtime-only scan against the **previous 127-version lock** on 15 November (the known vulnerable Soup Sieve 2.10 entry was subsequently removed):

| Package/version | Why runtime audit omitted it | Next evidence |
| --- | --- | --- |
| `iniconfig==2.3.1`, `nodeenv==1.12.0`, `pluggy==1.7.0`, `pyright==1.1.414`, `pytest==9.2.0`, `ruff==0.17.4` | Development/test tooling, excluded by `--no-dev` from the runtime export | Covered by complete lock-version audit |
| `colorama==0.4.6` | Windows-only selected dependency, not installed on Linux | Present in Windows lock inventory; also covered by complete audit |
| `pywin32==312` | Windows-only package, not installed on Linux | Windows audit checks it; also complete audit |
| `numpy==2.5.4`, `soupsieve==2.10` | Different lock variants from the versions selected by the tested runtime | Covered by complete audit |
| `httpx2-jsfetch==1.0` | Not selected/installed in either tested OS environment | Included in full lock-version audit; review its supported platform before deployment |

On Windows, `pywin32` was scanned; `colorama` was installed but excluded by the runtime-only audit. This table classifies **selection evidence**, not approved deployment scope or safe package behaviour. Use the exact per-runner JSON evidence for every version and marker; don't infer suitability on untested platforms.

The full-lock audit on the **current 126-version lock** must return a valid
126/126 result with **zero public findings** under `--fail-on-findings`.
Passing this gate does not certify security or package licences.

## 3. Two packages lacking machine-readable installed licence metadata

Both packages had **missing installed licence metadata** across all four previous CI environments. I independently inspected exact upstream release tags, not just package names.

| Package and locked version | Upstream versioned source evidence | Candidate licence, unapproved |
| --- | --- | --- |
| `agent-client-protocol==0.12.1` | [SDK LICENSE at tag 0.12.1](https://github.com/agentclientprotocol/python-sdk/blob/0.12.1/LICENSE), Git blob `d645695673349e3947e8e5ae42332d0ac3164cd7` | Apache License 2.0 |
| `tiktoken==0.14.0` | [LICENSE at tag 0.14.0](https://github.com/openai/tiktoken/blob/0.14.0/LICENSE), Git blob `83ed1036f70d4f419307e8a044a35e163cc35201` | MIT License |

This establishes **public upstream text at these tags only**, not legal permission for AEA's intended environment. An authorised reviewer must inspect the *actual pinned wheel/sdist contents*, licence notices and redistribution requirements and record an explicit organisation-specific decision. Do not inject the upstream labels into installed-wheel metadata as though verified.

## 4. CI action provenance

Four action families are pinned to upstream release commit SHAs in `.github/workflows/ci.yml`. The source SHA pins resist mutable tag substitution; they do **not** audit transitive Node dependencies, action runtime compatibility or CI trust boundaries. The release/security reviewer must validate the pinned code, whether fork PR permissions are appropriate and any necessary upgrade.

## 5. Confidential data and Windows permissions

AEA agents are **trusted Python code, not sandboxed**. Do not evaluate untrusted factories or tool providers with elevated privileges. The synthetic CI privacy tests do not prove that arbitrary case IDs, trace paths or tool/model identifiers are anonymised.

Reviewer must approve, in an access-controlled system:

- Input classification, permission to run the agent and outbound provider/network controls.
- Report/trace/baseline/raw `--capture-content` data policy, encryption, access restrictions, retention and deletion.
- Windows NTFS ACLs for generated runs, retained backups and directories, and recovery after a crash.
- Confidential-artefact rules: which summaries (if any) may be retained by GitHub Actions.
- Named security owner, explicit approve/reject decision, date, version/SHA, exceptions and re-review interval.

**Decision is not yet recorded.** Until that happens, use synthetic/local examples only. Do not change `master`, create a release tag or claim production readiness without explicit release-owner approval.

## 6. External pilot

[Issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) still requires **two independent real delivery-team integrations** and authorised reviews. The authors' two sample applications and automated timing reports are technical rehearsals, not evidence of external adoption or human productivity. See [pilot protocol](PILOT.md) and [human timecard](HUMAN_EFFORT_STUDY.md).

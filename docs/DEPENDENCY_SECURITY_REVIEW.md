# AEA 2.2.0: dependency and security self-assessment

**Prepared:** 14 November 2026. **Classification:** Engineering self-review, **not** an independent security certification.  
**Basis:** `pyproject.toml`, the versioned `uv.lock` at assessed `dev` commit `9eb93107fe481b6f7b60d00ad876d554c3f30794`, CI workflow, existing redaction and baseline safety tests.

## Dependency inventory

| Fact | Verified source state |
| --- | --- |
| Locked packages | **128 entries**, including one editable AEA project and **127** PyPI-registry package entries |
| Source origins | 127 registry entries from `https://pypi.org/simple`; one local editable project entry `.` |
| Version pins | Lock entries include explicit versions and SHA-256 artifact hashes for the 127 registry entries |
| Framework integrations | Optional `strands-agents`, `langgraph`, `langchain-core`, LangChain tracing instrumentation and optional `langchain-aws` |
| Core runtime | Inspect AI, OpenTelemetry SDK, Pydantic, JSON Schema, fsspec and a compatibility-pinned agent-client-protocol |
| Supported Python | 3.11+ declared; CI explicitly checks 3.11 and 3.12 only |
| Licence verification | The lock does not establish licence permissions or transitive licence compatibility; review needed |
| Public advisory scan | [CI #43627751480](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43627751480) scanned **116** exported Python package entries and reported **0 known advisories**. This is narrower than the 127 locked registry entries and is not full security clearance. |

Inventory counts describe **locked variants and optional dependency groups**, not necessarily the number of packages installed for every runtime/platform combination.

## Observed advisory result and remaining coverage

In [the PR #124 CI scan](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43627751480), the pinned public auditor reported **116 scanned entries, zero published advisory records returned and zero affected packages** for its exported all-extras runtime requirements view on Ubuntu Python 3.11. The scan produced the `aea-public-advisory-scan` artefact with the JSON and Markdown result. The lockfile separately contains **127** PyPI registry entries: platform markers, optional selection and export treatment mean these are not interchangeable package populations. Do not infer that the unscanned variants, future advisories, licences or malicious releases are cleared.

The scan's status is `no_known_findings_in_scanned_set`, **not** `security_approved`. A formal independent vulnerability, licence and policy review is still required.

## Reproducible assessment

```sh
uv lock --check
uv export --frozen --all-extras --no-dev --no-emit-project --format requirements.txt --output-file aea-audit-requirements.txt
```

The export is a temporary requirements view, not an additional dependency source of truth. Review whether conditional markers and optional extras are relevant to the deployment.

For a reproducible scan with the exported dependency set, AEA provides the following wrapper. Its results are uploaded by CI as **review-only public advisory evidence**, and it never auto-upgrades dependencies.

```sh
uv run --locked python scripts/dependency_inventory.py --output-dir new-inventory-folder
uv run --locked python scripts/audit_public_advisories.py --output-dir new-advisory-folder
```

The advisory scanner treats network errors or missing results as errors, and serialises known findings into a JSON and Markdown report. A successful workflow **does not imply zero known vulnerabilities**: findings are recorded for triage without automatic remediation, and the separate security reviewer must approve any resolution. The scan is for one exported runtime requirements selection with all extras, not a full multi-platform, licence or malicious-package review.

For a current vulnerability database assessment in an approved network environment, use a separately pinned auditor such as `pip-audit` against the exported, fully pinned dependencies:

```sh
uvx --from pip-audit==2.10.1 pip-audit --requirement aea-audit-requirements.txt --no-deps --disable-pip --format json --output aea-audit-results.json
```

**Important:** Advisory results are date- and source-dependent. The scanner may return non-zero when vulnerabilities are found. Do not interpret a failed network lookup or incomplete package collection as “no vulnerabilities”. Do not use `--fix` on a production branch without reviewing resulting lockfile changes. These commands contact external package/advisory services. Remove locally exported artefacts under an approved handling policy; never commit the generated results without review.

For a second independent source or where organisational tooling requires it, export the locked packages in the approved SBOM format and run the organisation's licence and supply-chain tooling. `uv.lock` alone cannot validate package licences, supply-chain provenance or malicious releases.

## CI action provenance and licence metadata evidence

Every third-party action invoked by `.github/workflows/ci.yml` is now pinned
to a **full reviewed upstream release commit SHA**, verified against official
GitHub tag refs on 15 November 2026:

| Action | Version | Verified commit |
| --- | --- | --- |
| `actions/checkout` | v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/setup-python` | v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/upload-artifact` | v4.6.2 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `astral-sh/setup-uv` | v6.8.0 | `d0cc045d04ccac9d8b7881df0226f9e82c39688e` |

This removes mutable major-version tags in CI, not the need to review
upstream code, action transitive dependencies, or future updates.

The new `scripts/dependency_licence_sbom.py` generates a **review-only**
CycloneDX 1.5 inventory containing every locked registry variant, with
installed/not-installed provenance and licence expressions/classifiers from
the current Python environment. CI saves separate manifests for Windows and
Linux, Python 3.11 and 3.12. It does **not** claim that metadata classifiers
establish licence permissions, nor that all locked variants are installed in
each matrix cell. Missing licence metadata, platform selection and mismatched
versions are explicit evidence fields.

To run manually from the checkout:

```sh
uv run --locked python scripts/dependency_licence_sbom.py --output-dir new-review-only-sbom
```

Retain these only in approved locations. An authorised licence reviewer must
approve policy, exceptions and transitive licence compatibility; an independent
security owner must approve live data handling and Windows NTFS controls.
The public advisory scanner remains observational and is still scoped to its
exported dependency set, not a universal clearance.

## Cross-platform public advisory coverage (engineering evidence)

CI now executes a separate public advisory scan in each supported runtime
combination: Windows and Ubuntu with Python **3.11 and 3.12**. The scanner
records each assessed **package name and exact locked version**, the current
interpreter/platform and scan date. `scripts/assess_advisory_coverage.py`
reconciles those identities against the complete lockfile and separately
installed variants reported by the platform's CycloneDX evidence.

Each job retains an `aea-platform-advisory-OS-pyVERSION` evidence artefact
for 14 days, containing the dated advisory result and a short coverage report.
The coverage reports explicitly list unscanned locked variants and any
installed-but-unscanned versions. An empty or duplicated advisory inventory
is treated as an invalid scan, **not a clean security result**. The pinned
auditor runs using that CI job's Python interpreter.

This work improves visibility, but is not proof of full advisories coverage,
licence-policy approval, dependency safety on other Python versions or an
authorised security review. Development-only dependencies, platform variants
and public advisory feed limitations require separate evaluation.
The original release acceptance scan remains for backwards compatibility.

## Entire lockfile advisory coverage and licence exceptions

The `scripts/audit_all_locked_variants.py` command now audits **every locked
PyPI package name/version**, including development dependencies and
platform-/Python-alternative versions. Versions of one package are separated
into different audit batches; the script then checks all returned package
identities against the source lock before writing evidence. No dependency is
installed or upgraded. The release CI job saves a dated 14-day summary.

```sh
uv run --locked python scripts/audit_all_locked_variants.py --output-dir new-full-lock-advisory-folder
```

The prior per-runner runtime views remain useful for platform deployment
selection, but they cover only 116/127 (Linux) and 117/127 (Windows) locked
versions. The complete audit closes the *inventory coverage* gap for public
advisories, **not** the possibility of undisclosed vulnerabilities or malicious
packages.

The two installed package metadata omissions are
`agent-client-protocol==0.12.1` and `tiktoken==0.14.0`. Their **exact upstream
tagged licence files** are now cited in
[the security approval handover](SECURITY_APPROVAL_HANDOFF.md). These are
candidate licence identifications, not verified wheel/sdist terms or permission
to use/distribute them. The handover also records platform exclusions, NTFS,
data retention, CI action dependencies and the remaining approval fields.

## Security boundaries and remaining findings

| Priority | Boundary or risk | Status / next action |
| --- | --- | --- |
| P1 | Trusted imported Python factories, mappings and scorers execute code in the AEA process | Architecture limitation, **not sandboxed**; require reviewed sources and least-privilege environments |
| P1 | Default logs/traces minimise payloads but retain possible identifiers (case IDs, tool and model names, paths, numerical metadata) | Synthetic sentinel checks pass; classify outputs before real data |
| P1 | Explicit `--capture-content` persists raw prompts/tool payloads | Opt-in only; define access control, encrypted storage and retention before confidential use |
| P1 | Windows file ACLs and backup storage policy have not been approved | New POSIX snapshots use restricted modes; obtain NTFS ACL policy and retention owner |
| P2 | Baseline activation can briefly remove the active path even when cooperating writers are locked | [Issue #123](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/123) covers concurrent readers and a compatibility-safe redesign |
| P2 | Advisory vulnerability and transitive dependency licence review not yet formally signed off | Execute dated scans, triage fixes and document exceptions |
| P2 | CI Actions pinned to verified commit SHAs | Implemented; update pins only after reviewing upstream changes |
| P2 | Live providers, network timeouts, quota handling and real model-usage costs | Require approved provider tests; not exercised by no-cost CI |

## Required release approvals

The **security owner** must approve data classification, provider permissions, log/trace access, backup retention, Windows ACLs and accepted vulnerability findings. The **release owner** must approve any change to `master`, tag, package distribution and intended customer scope. A real **independent pilot** is required to claim multi-team adoption.

**Decision:** Continue synthetic local demonstrations only. No customer data or production use authorised by this self-assessment.

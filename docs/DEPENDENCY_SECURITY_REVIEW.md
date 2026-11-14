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
| Vulnerability status | **Unknown until a dated advisory scan completes.** SHA-256 hashes and a green CI do not prove absence of known CVEs |

Inventory counts describe **locked variants and optional dependency groups**, not necessarily the number of packages installed for every runtime/platform combination.

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

## Security boundaries and remaining findings

| Priority | Boundary or risk | Status / next action |
| --- | --- | --- |
| P1 | Trusted imported Python factories, mappings and scorers execute code in the AEA process | Architecture limitation, **not sandboxed**; require reviewed sources and least-privilege environments |
| P1 | Default logs/traces minimise payloads but retain possible identifiers (case IDs, tool and model names, paths, numerical metadata) | Synthetic sentinel checks pass; classify outputs before real data |
| P1 | Explicit `--capture-content` persists raw prompts/tool payloads | Opt-in only; define access control, encrypted storage and retention before confidential use |
| P1 | Windows file ACLs and backup storage policy have not been approved | New POSIX snapshots use restricted modes; obtain NTFS ACL policy and retention owner |
| P2 | Baseline activation can briefly remove the active path even when cooperating writers are locked | [Issue #123](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/123) covers concurrent readers and a compatibility-safe redesign |
| P2 | Advisory vulnerability and transitive dependency licence review not yet formally signed off | Execute dated scans, triage fixes and document exceptions |
| P2 | CI Actions use version tags for checkout, Python setup and uv setup | Consider pinning to reviewed immutable commit SHAs in a separate workflow-hardening change |
| P2 | Live providers, network timeouts, quota handling and real model-usage costs | Require approved provider tests; not exercised by no-cost CI |

## Required release approvals

The **security owner** must approve data classification, provider permissions, log/trace access, backup retention, Windows ACLs and accepted vulnerability findings. The **release owner** must approve any change to `master`, tag, package distribution and intended customer scope. A real **independent pilot** is required to claim multi-team adoption.

**Decision:** Continue synthetic local demonstrations only. No customer data or production use authorised by this self-assessment.

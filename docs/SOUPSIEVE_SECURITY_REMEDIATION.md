# Soup Sieve vulnerability discovered and remediated

**Status:** Technical remediation on the `dev` candidate branch, subject to merged
CI checks. This is **not** independent security sign-off.

## Finding

The 15 November 2026 first **full lockfile** advisory run checked 127/127
registry package versions and discovered **three published advisories** on
`soupsieve==2.10`. The older pinned version existed only for the old
`python_full_version < '3.11.5'` resolution branch, which no earlier CI
runner exercised.

| Public advisory | Type and impact | Fixed upstream |
| --- | --- | --- |
| [CVE-2026-126190](https://github.com/advisories/GHSA-mmhr-3c5m-f64f) | High, polynomial-cost selector matching | Soup Sieve 4.0+ |
| [CVE-2026-126191](https://github.com/advisories/GHSA-6655-6qjp-jx7x) | High, regex backtracking when compiling untrusted selectors | 3.0.2+ |
| [CVE-2026-126193](https://github.com/advisories/GHSA-7g44-g9rc-x53w) | Medium, recursive selector parsing | 3.0.2+ |

Source: the prior PR #134 `aea-complete-lock-advisories` CI artefact
(`127/127` locked variants, 3 public advisory findings, dated 2026-11-15).

## Fix

1. Raise the declared Python support floor from `>=3.11` to **`>=3.11.5`**.
   Python 3.11.0-3.11.4 is no longer supported. Use an updated Python 3.11
   patch release or Python 3.12 for local setup.
2. Re-resolve `uv.lock` with pinned **uv 0.10.0** using the temporary,
   branch-scoped GitHub Actions lock refresh. The temporary workflow was
   deleted immediately after regenerating the lock.
3. The updated lock contains **`soupsieve==4.1` only**. The vulnerable 2.10
   conditional branch and its obsolete Python <3.11.5 resolver marker were
   eliminated. No alternative vulnerable package version is retained.
4. Add a unit safety check asserting the Python floor agrees with `uv.lock`
   and Soup Sieve 2.10 cannot silently return.
5. Change the complete lock-version public advisory CI gate to use
   `--fail-on-findings` so **any known future advisory fails release acceptance**
   after preserving its review evidence.

Current complete lock count: **127 package records in total**, including one
local AEA root and **126 PyPI-registry package version entries**. The final
full-lock audit result must independently confirm every one of the 126
registry entries and no known public advisories before technical approval.

## Important boundaries

This removes the *known vulnerable conditional dependency selection* from the
supported lockfile; it is not an assertion that all dependencies are
vulnerability-free, that attacker-controlled selectors are safe in other
libraries, or that real customer data can be processed. Production still
requires an authorised dependency/licence/security review, data-retention
decision, NTFS ACL policy and independent pilots tracked in
[issue #125](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/125)
and [release gate #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111).

**Operator action for an older local Python installation:** upgrade the
interpreter to at least Python 3.11.5 before running setup. Never bypass
`uv lock --check` or temporarily re-enable the old locked version.

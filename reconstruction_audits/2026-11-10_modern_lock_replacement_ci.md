# Generated dependency lock and replacement CI — 10 November 2026

**Nature:** Newly authored, separately reviewable engineering validation. This is **not** part of the original v2.2.0 source-video transcript.

## Why original uv.lock is unnecessary for functional recovery

The original historical `uv.lock` was not supplied and the user cannot upload or transcribe a multi-thousand-line generated file. Requiring it would not improve the fidelity of source code or API behaviour. A new resolver can select package versions satisfying the recovered `pyproject.toml`, and native reconstructed tests can validate that installed resolution on real platforms.

**Important distinction:** An installation using `uv lock` today demonstrates present-day compatibility. It does **not** reproduce exactly which library versions were originally used, or establish that the lost historical dependency graph was safe.

## New CI replacement

`.github/workflows/reconstruction-modern-lock-ci.yml` runs on PRs into the reconstruction review branch. On **Windows and Ubuntu, Python 3.11 and 3.12**, it:

1. Fails closed if a `uv.lock` is already present at the checked-out historical path.
2. Installs a pinned `uv` resolver and generates a **new temporary** lock from the current `pyproject.toml`.
3. Installs runtime/framework/dev dependencies with `uv sync --all-extras --group dev --locked`; no paid provider keys.
4. Gates Ruff lint, Pyright and formatting of newly authored reconstruction-test source. The original recovered source contains four **pre-existing Ruff formatter differences** (cli.py, compare.py, judge.py, readings.py); its formatter output remains an **explicit non-gating diagnostic** rather than silently rewriting video-derived source. Also runs README safety tests, the native offline integrated suite through a new **safe synthetic-fixture wrapper** (with checksum-guarded cleanup), and the seven-example regression replay.
5. Prints the SHA256 of the generated lock and uploads it as a **seven-day CI artifact** for reviewers.
6. Never pushes this file to the repository, and has `contents: read` permission only.

The CI artifact is useful to investigate a dependency drift or repeat an individual CI run with that resolution. It is **not** the original `uv.lock`.

## Original historical CI remains blocked

`scripts/ci.sh` and `reconstruction_drafts/original_github_workflows_ci.yml.txt` are historical evidence and remain unchanged. Their locked dependency and authentic baseline requirements are intentionally not bypassed or silently rewritten.

The new workflow is the recommended engineering substitute while provenance gaps remain. Final release approval still depends on security/privacy review, signoff and real delivery-team validation. The existence of a new lockfile or passing tests does not approve a merge into `master`.

Historical inventory remains **97/117 original paths**; this work recovers **zero additional original paths**. The root README is now newly authored operational documentation and is marked as such; it does not certify historical README source bytes.

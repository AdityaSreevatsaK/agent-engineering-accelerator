# Historical CI activation readiness (9 November 2026)

The recorded original GitHub workflow is preserved at `reconstruction_drafts/original_github_workflows_ci.yml.txt`, not at `.github/workflows/ci.yml`. Its prior activation failed when `uv sync --all-extras --locked` found no historical `uv.lock`.

Current historical inventory is **97 of 117 original paths**. Missing paths consist of 14 baselines, two calculator captured-log fixtures, `uv.lock`, `docs/acceptance.md`, `docs/review.md`, and the original workflow path.

Before reactivation, verify: a valid lockfile; the original baseline logs and their provenance; original calculator fixtures or explicit documentation of deferred tests; and a faithful workflow transcription. Do not replace historical artefacts with generated lookalikes.

This is an evidence/readiness note, not a historical source file, and does not increase original-path recovery count. Keep the release branch `master` unchanged.

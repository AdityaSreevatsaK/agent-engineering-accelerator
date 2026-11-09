# Original CI and seven documentation recordings (9 November 2026)

Source: User-provided Notepad++ video recordings, reconstructed as source candidates.

## Restored historical paths

- `scripts/ci.sh`: preserved as recorded, Bash syntax checked; may differ in one character from original editor total. Its `uv sync --all-extras --locked` needs the original `uv.lock` before execution.
- `CHANGELOG.md`: reconstructed from the recorded scrolling video; lengthy source remains subject to line-by-line historical fidelity audit.
- `examples/expense/README.md`, `examples/helpdesk/README.md`, `examples/policy_rag/README.md`, `examples/triage/README.md`: restored from supplied videos; Markdown file structure and relative references should be checked as release validation.

## Historical GitHub Actions workflow: stored, but intentionally not activated

- The original `.github/workflows/ci.yml` video source was restored at the historical path in the first PR revision.
- That activated a new mandatory workflow `ci`. It failed on GitHub Action run 42636267977 while executing `uv sync --all-extras --locked` because the historical `uv.lock` is missing from reconstruction.
- To avoid introducing a guaranteed failing branch workflow, exact recovered content was preserved under `reconstruction_drafts/original_github_workflows_ci.yml.txt`, and the active `.github/workflows/ci.yml` was removed from this PR.
- The original CI workflow path is **not** counted as historically restored. Its source is archived pending reconstruction of the original lockfile and other historical baselines.
- The historical source was **not** changed to evade tests, and the existing green AEA reconstruction CI workflows remain active.

## Scope, limitations and policy

- Six historical paths from this batch are newly restored; if merged, the canonical historical-path inventory increases from 89 to **95/117** (path presence only).
- The archived historical CI is separate from that count.
- Do not claim exact original byte fidelity for video-derived text; functional documentation checks and future line-by-line reviews are separate.
- The original calculator capture fixture JSON files cannot be provided, by user confirmation; no fabricated originals.
- Never activate the historical workflow until missing dependencies and input files are resolved. Keep `master` unchanged.

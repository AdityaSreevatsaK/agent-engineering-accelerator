# AEA reconstruction checkpoint | 5 November 2026 | Part 30: distributable wheel and installed CLI

**Repository:** `AdityaSreevatsaK/agent-engineering-accelerator`  
**Reconstruction branch:** `reconstruction/wip-checkpoint-2026-10-30`  
**Master:** unchanged by this work  
**Scope:** verified packaging and installed-CLI behaviour of reconstructed AEA v2.2.0, **not** historical source fidelity or complete release acceptance.

## Work delivered

**PR #18:** https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/18  
**Merged into reconstruction branch:** `879da39ce8d95bb29d17b20beef00168155d6a6b`.

GitHub's changed-filename list confirms **only** two files were merged:

1. `reconstruction_tools/verify_wheel_install.py`
2. `.github/workflows/reconstruction-wheel-cli.yml`

There were **no production source changes**, historical video-draft edits or modifications to `master`.

The new Windows/Ubuntu × Python 3.11/3.12 workflow builds a **real distributable wheel** using the declared `uv_build` PEP 517 backend. It then creates a completely new temporary virtual environment **outside the repository checkout**, installs the built wheel with its declared dependencies, and tests:

- Installed distribution metadata exactly matches `agent-accelerator==2.2.0`.
- The wheel includes the required `agent_accelerator/template/agent.py` and `dataset.jsonl`, and their **raw bytes match** the checked-in source files at build time.
- The installed `aea` console entry point exists, is importable from its new virtual environment and exposes the expected commands.
- `aea init` and `aea init --force` create/restore expected starter templates from the installed distribution.
- `aea export --format html` produces an offline HTML file without a real browser; raw untrusted `<script>` markup is absent and escaped text is preserved.

No AWS/cloud credentials, real model APIs, historical fixture contents or user/client data were used. The helper creates temporary scratch files only.

## Failure-driven verification correction

The initial GitHub wheel workflow on Windows/Python 3.12 failed on `aea init template differs from source: agent.py`. Investigation showed it was a **test-harness portability issue**, not a demonstrated CLI defect: raw Windows working-tree source bytes can be CRLF while `aea init` explicitly writes LF.

Corrected **only the smoke-test helper** to compare generated template **text** with universal-newline reading, while retaining the separate, unchanged **raw wheel-vs-source byte comparison**. Also applied this text comparison to the `--force` case.

## Verified native CI

Final wheel workflow run **`42085247737`** completed successfully. Each actual job log contains the same success acknowledgement:

`PASSED: wheel agent_accelerator-2.2.0-py3-none-any.whl; fresh installed CLI, metadata, bundled templates, init/force, and HTML escaping.`

| Environment | Wheel build + fresh-install smoke |
| --- | --- |
| Ubuntu / Python 3.11 | Passed |
| Ubuntu / Python 3.12 | Passed |
| Windows / Python 3.11 | Passed |
| Windows / Python 3.12 | Passed |

All four logs were individually fetched and checked. The candidate's **five inherited workflows** were also reported successful across all four Windows/Linux Python combinations:

- Integrated active unit suite, run **`42085247607`**, **1,075 passed, 60 deselected, 61 warnings** per environment; each of the four pytest logs was checked.
- Framework adapters, run **`42085247598`**.
- Build/run/scrub synthetic fixture, run **`42085247613`**.
- Fixture-independent comparison/statistics, run **`42085247568`**.
- Judge/report/CLI/export/readings regression, run **`42085247584`**.

**Result: 24 of 24 GitHub Actions matrix jobs passed on PR #18's final commit.** These overlapping CI workflows do **not** increase the unique test count beyond the integrated 1,075-case baseline.

## Remaining reconstruction and release limits

- Original calculator agent and dataset, original captured/broken JSON fixtures, and triage/expense example configs are still unrecovered. The 60 explicitly deselected cases do **not** count as passing, and CI-only synthetic data must never be presented as the original files.
- Historical `test_cli.py` remains partial after line 364 and `test_judge_pairwise.py` after line 509; original footage or raw files are still needed for source-level reconstruction.
- Marked slow/subprocess tests are excluded by `-m not slow`.
- `README.md` still contains only the repository title and is **not** a complete user/operator manual; baseline fixtures, remaining historical examples, documentation and original source correctness have not been reconciled.
- Packaging and core offline behaviour are now genuinely verified, but no real provider/cloud integration has been executed.
- Do **not** merge the entire reconstruction branch into `master` or call the v2.2.0 reconstruction complete until original evidence, missing files, slow/integration tests and fidelity review are resolved.

## Next practical work

1. Recover the user's remaining video recordings/original fixtures and complete partial transcription.
2. Use the restored original logs to enable all 60 deferred test cases.
3. Add independently controlled offline slow/integration tests and run static quality checks without disguising source discrepancies.
4. Produce operator documentation and an end-to-end demonstration only after identifying original versus newly created material.

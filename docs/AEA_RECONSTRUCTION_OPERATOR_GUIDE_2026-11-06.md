# AEA reconstruction: offline operator guide

**Checkpoint:** 6 November 2026  
**Code branch:** `reconstruction/wip-checkpoint-2026-10-30`  
**Scope:** The *reconstructed*, locally runnable AEA 2.2.0 starter. This is not an original-source fidelity sign-off or a production release.

## Prerequisites

- Windows or Linux with Python 3.11 or 3.12.
- Clone this repository and check out the reconstruction branch.
- Install the package, Inspect AI and the Strands integration:

```bash
python -m pip install -e ".[strands]"
```

The following commands use the **built-in deterministic offline Strands model double**. They do not use AWS credentials, cloud infrastructure or paid model providers.

## Local walkthrough

Run all commands from the repository root.

```bash
python -m agent_accelerator.cli init demo_agent

python -m agent_accelerator.cli check demo_agent/dataset.jsonl --agent demo_agent.agent:build_offline_agent --runs-dir runs --baseline baseline --update-baseline

python -m agent_accelerator.cli check demo_agent/dataset.jsonl --agent demo_agent.agent:build_offline_agent --runs-dir runs --baseline baseline
```

The first `check` stores a local scrubbed baseline; the second performs a deterministic run and compares it with that baseline. The starter dataset contains five declared cases. A successful smoke produces `passed=5/5` and a `comparison.md` file in the latest run directory.

The run directory path is printed in the CLI output. Substitute that path into these examples:

```bash
python -m agent_accelerator.cli report PATH_TO_RUN_DIRECTORY
python -m agent_accelerator.cli compare baseline PATH_TO_RUN_DIRECTORY --output comparison-copy.md
python -m agent_accelerator.cli export PATH_TO_RUN_DIRECTORY/report.md --format html --output offline-report.html
```

Use the paths relevant to your terminal. In PowerShell, paths can also be quoted with backslashes.

## Repeatable automated demonstration

```bash
python reconstruction_tools/verify_offline_template_e2e.py
```

The automated demonstration uses a disposable temporary folder, so it does not change historical fixtures, checked-in examples or local baseline directories. It exercises initialisation, two five-case runs, baseline creation, regression checking, comparison, Markdown reporting and HTML export. The corresponding GitHub Actions workflow runs on Windows and Ubuntu with Python 3.11 and 3.12.

## Current verification boundary

| Verified | Not yet verified |
| --- | --- |
| Installed AEA wheel and console entry point | Original v2.2.0 source byte equality |
| Offline Strands starter and declared five cases | Real AWS/provider requests or deployment |
| Deterministic baseline, comparison and report flow | Original calculator capture and broken-log fixture assertions |
| HTML report generation | Full historical examples, baselines and slow subprocess test inventory |
| Windows/Linux Python 3.11/3.12 CI | Unrecorded source portions of the original CLI and pairwise judge tests |

**Privacy:** The CLI's `--capture-content` option retains prompts and outputs. Do not commit logs containing client or personal content. The walkthrough does not require that option.

This document was newly authored during reconstruction and must not be represented as a recovered historical project file.

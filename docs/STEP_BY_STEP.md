# AEA: Simple step-by-step guide

## Before you start

You need:

- **Windows PowerShell** (open it from the Start menu). Use PowerShell, not Command Prompt, for these commands.
- **Python 3.11.5 or newer** (Python 3.12 also works) and **Git** installed. Older Python 3.11 patch releases are not supported because their original dependency selection included a vulnerable library.
- An **internet connection** for the first installation and permission to access the GitHub repository.

**You do not need:** Docker, WSL, AWS/OpenAI accounts, API keys or a paid model for the examples.

**How to use this guide:** Complete **Step 0 once**, then choose any flow below. Paste the commands into the **same PowerShell window**. You do **not** need to change Python files for the included examples.

If you repeat a flow, change its output folder name from `-001` to `-002`. The scripts deliberately refuse to overwrite previous results.

## 0. Checkout, install and check the environment

**Step 1.** Open **Windows PowerShell**.

**Step 2.** Copy and paste this whole block:

```powershell
py -3.11 --version
# Confirm the version is 3.11.5 or newer before continuing
git --version
git clone --branch dev https://github.com/AdityaSreevatsaK/agent-engineering-accelerator.git
Set-Location agent-engineering-accelerator
py -3.11 -m pip install uv==0.10.0
uv --version
uv lock --check
uv sync --python 3.11 --all-extras --group dev --locked
uv run --locked aea --help
```

**Expected:** The final command displays the AEA commands. Installation is complete.

If `py` or `git` is not recognised, install the missing prerequisite first. If `uv` is not recognised after installation, reopen PowerShell and go back to the repository folder. If you have already cloned AEA, open that folder on the `dev` branch instead of cloning again. Do not discard local changes.

**Step 3.** Keep PowerShell open and choose a flow.

## A. Run a complete leadership demonstration

**What it does:** Creates a passing test, deliberately breaks an agent, and makes a readable HTML report.

**Paste:**

```powershell
uv run --locked python scripts/leadership_demo.py --output-dir demo-001
Invoke-Item .\demo-001\regression-report.html
```

**Expected:** `PASS`, 11/11 normal test cases, a detected regression and a browser report.

**Results:** `demo-001/DEMO.md`, `regression-report.html` and `evidence.json`.

## B. Full AWS Strands equipment warranty flow

**What it does:** Runs 12 test cases, saves a baseline, checks it again and catches a known warranty error. It uses a local Strands model, **not AWS**.

**Paste:**

```powershell
uv run --locked python scripts/validate_independent_integrations.py --only equipment-strands --repeats 1 --output-dir strands-001
Get-Content .\strands-001\evidence.json
```

**Expected:** `PASS equipment-strands`, 12/12 normal cases, one clean repeat, a detected regression and an unchanged baseline.

**Results:** `strands-001/evidence.json` and the regression report under `strands-001/equipment-strands/runs/`.

## C. Full LangGraph supplier onboarding flow

**What it does:** Tests a LangGraph agent with custom input/output mapping and catches a known supplier-screening error.

**Paste:**

```powershell
uv run --locked python scripts/validate_independent_integrations.py --only vendor-langgraph --repeats 1 --output-dir langgraph-001
Get-Content .\langgraph-001\evidence.json
```

**Expected:** `PASS vendor-langgraph`, 12/12 normal cases, one clean repeat, a detected regression and an unchanged baseline.

**Results:** `langgraph-001/evidence.json` and the regression report under `langgraph-001/vendor-langgraph/runs/`.

**Want to test both frameworks together?** Paste:

```powershell
uv run --locked python scripts/validate_independent_integrations.py --repeats 2 --output-dir both-001
Get-Content .\both-001\evidence.json
```

## D. Generate a new agent without editing or cloud credentials

**What it does:** Creates a working example agent, runs five tests, saves a baseline and opens an HTML report. This starter uses the bundled **offline** model.

**Paste:**

```powershell
uv run --locked aea init starter_agent_001
uv run --locked aea doctor starter_agent_001/dataset.jsonl --adapter strands --agent starter_agent_001.agent:build_offline_agent
uv run --locked aea check starter_agent_001/dataset.jsonl --adapter strands --agent starter_agent_001.agent:build_offline_agent --baseline starter_baseline_001 --runs-dir starter_runs_001 --max-samples 1 --update-baseline
uv run --locked aea check starter_agent_001/dataset.jsonl --adapter strands --agent starter_agent_001.agent:build_offline_agent --baseline starter_baseline_001 --runs-dir starter_runs_001 --max-samples 1
uv run --locked aea export starter_baseline_001/report.md --format html --output starter_report_001.html
Invoke-Item .\starter_report_001.html
```

**Expected:** `PASS: preflight complete`, 5/5 cases, `OK: baseline` and a browser report.

**Results:** `starter_agent_001/` contains the generated code, `starter_baseline_001/` contains the reference report, and `starter_report_001.html` is ready to open.

**One-command automatic check** (runs the same starter lifecycle in a temporary folder):

```powershell
uv run --locked python scripts/verify_starter_walkthrough.py
```

## E. Run unit, integration, privacy and package checks

**What it does:** Runs the project's local developer and release tests.

**Paste:**

```powershell
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/run_checks.py --slow
uv run --locked python scripts/check_examples.py
uv run --locked python scripts/check_privacy_e2e.py
uv run --locked python scripts/verify_runbook_console.py
uv build --wheel
uv run --locked python scripts/check_distribution.py
```

**Expected:** Every command completes successfully. The wheel check prints `PASS: built wheel`. The slower tests may take longer.

**For the latest CI results**, see [GitHub Actions](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions).

## F. Run both frameworks and a repeated regression pilot

**What it does:** Repeats the Strands and LangGraph calculator checks three times and confirms that known bad agents are rejected.

**Paste:**

```powershell
uv run --locked python scripts/pilot_rehearsal.py --output-dir rehearsal-001 --repeats 3
Get-Content .\rehearsal-001\REHEARSAL.md
```

**Expected:** `PASS` for both frameworks, three clean reruns and a detected intentional regression.

**Results:** `rehearsal-001/REHEARSAL.md` and `evidence.json`.

## G. Compare AEA with native QA and measure runtime

**What it does:** Measures test execution time and checks whether AEA and direct framework tests find the same deliberate defects.

**Paste:**

```powershell
uv run --locked python -m scripts.benchmark_agent_evaluations --repeats 3 --output-dir benchmark-001
Get-Content .\benchmark-001\BENCHMARK.md
uv run --locked python -m scripts.controlled_pilot_study --repeats 3 --output-dir comparison-001
Get-Content .\comparison-001\STUDY.md
```

**Expected:** Both finish with `PASS`. The comparisons agree on the deliberately failing cases.

**Results:** `benchmark-001/` and `comparison-001/`. These are **computer execution timings**, not time saved by developers.

## H. Measure scripted onboarding and review the results

**What it does:** Times dependency setup and the first working report for the two sample frameworks.

**Paste:**

```powershell
py -3.11 -m scripts.onboarding_rehearsal --output-dir onboarding-001
Get-Content .\onboarding-001\ONBOARDING_REHEARSAL.md
```

**Expected:** `PASS` for Strands and LangGraph, with seconds recorded for each step.

**Results:** `onboarding-001/ONBOARDING_REHEARSAL.md` and `evidence.json`. Previously downloaded packages may be cached. This does **not** measure human onboarding effort.

## I. Connect an existing application to AEA

**This flow needs your own application.** The examples above run without edits, but AEA cannot automatically invent your real agent and its expected answers.

1. Expose a Python function such as `agent:build_agent` that creates your existing Strands agent or LangGraph graph.
2. Provide a `dataset.jsonl` containing the questions and expected results. Use an `aea.toml` containing the framework and factory name.
3. From the directory containing your application, use the following sequence after installing AEA in that environment:

```powershell
aea doctor dataset.jsonl --config aea.toml
aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1
```

**Expected:** The preflight succeeds, the first command saves a baseline and the final command reports `OK: baseline` if behaviour is unchanged.

For real applications, see [agent setup and supported case formats](USAGE.md) and [LangGraph mapping examples](../integrations/vendor_langgraph/README.md). Keep paid providers and confidential data out of unapproved test runs.

## J. Inspect backups, recovery and release gates

**What it does:** Checks whether a previous version of the sample baseline was retained.

After completing flow D, **paste:**

```powershell
uv run --locked aea backups starter_baseline_001
```

**Expected:** A read-only list. After the first baseline, it usually says there are no previous backups.

Never delete a backup or lock file just to resolve an error. Use [recovery instructions](OPERATIONAL_READINESS.md). Real-team adoption and security approval are still required before an internal production release.

## Troubleshooting and interpretation

- **`uv`, `git` or `py` not recognised:** Install the missing prerequisite or reopen PowerShell.
- **Output folder already exists:** Change `-001` to `-002` in the relevant commands. Previous results are not deleted.
- **Unexpected `REGRESSION`:** Read the generated comparison report. The deliberate faulty-agent test in flows B, C and F is expected to trigger a regression.
- **Import or mapping error:** Use the provided example first. For your own application, check the working directory and `aea.toml`.
- **Need Linux/macOS commands?** See [the alternative terminal instructions](ONBOARDING.md).

**Privacy:** The samples use synthetic data. Reports can still contain case IDs, file paths and tool names. Do not publish raw logs or use confidential customer inputs without approval.

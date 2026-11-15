# AEA: complete step-by-step workflows

**Branch:** `dev` (development candidate v2.2.0). **Scope:** Local, synthetic, no paid model calls. **Primary machine:** Native Windows PowerShell, no WSL needed. All commands are from the repository root unless a section says otherwise.

This is the operational entry point. Select a flow and follow the commands in order. **You do not need to edit code or supply API keys for flows A to H.** Flow I, connecting an unrelated existing agent, necessarily requires that application's importable code and an approved dataset. Real delivery-team adoption and security sign-off cannot be manufactured or automated.

## Find the right flow

| Flow | Goal | What it produces | Requires a real agent or external approval? |
| --- | --- | --- | --- |
| [0. Install](#0-checkout-install-and-check-the-environment) | Fetch the development candidate and dependencies | A working `aea` CLI | Repository access, Git/Python/uv installation |
| [A. Fast demonstration](#a-run-a-complete-leadership-demonstration) | Show a passing and a deliberately broken agent | HTML, Markdown, JSON, run evidence | No |
| [B. Strands](#b-full-aws-strands-equipment-warranty-flow) | Doctor → freeze → compare → detect defect | 12-case evaluation and regression | No |
| [C. LangGraph](#c-full-langgraph-supplier-onboarding-flow) | Custom-state mapping plus quality gate | 12-case evaluation and regression | No |
| [D. Generate a starter](#d-generate-a-new-agent-without-editing-or-cloud-credentials) | `aea init` → doctor → check → report → export | Fully working 5-case offline starter | No |
| [E. Complete automated test suite](#e-run-unit-integration-privacy-and-package-checks) | Run the same offline technical checks as CI | Test pass/fail output | No |
| [F. Regression and pilot rehearsal](#f-run-both-frameworks-and-a-repeated-regression-pilot) | Two-framework reproducibility | Summary and baseline evidence | No |
| [G. Comparisons and benchmarking](#g-compare-aea-with-native-qa-and-measure-runtime) | Synthetic execution times and defect parity | Local Markdown/JSON | No |
| [H. Installation/onboarding measurements](#h-measure-scripted-onboarding-and-review-the-results) | Machine-measured first report | Local Markdown/JSON | No |
| [I. Your existing application](#i-connect-an-existing-application-to-aea) | Evaluate a non-example agent | Project-specific baseline and regression | Yes, genuine code and test cases |
| [J. Recovery and release decisions](#j-inspect-backups-recovery-and-release-gates) | Read-only backup inventory and review gates | Operational evidence | Authorised decisions for real deployments |

**Important:** Flows that generate a directory refuse to overwrite an existing path. Use the example name on a fresh checkout; for a second attempt use a **new name**, such as `demo-evidence-002`. Never delete directories, remove locks or reset baselines to make a command succeed.

## 0. Checkout, install and check the environment

### 0.1 Prerequisites

You need **Git**, **Python 3.11 or 3.12**, a terminal and initial internet access for the repository and pinned Python packages. Windows PowerShell is sufficient. A GitHub login/authorisation is required if the repository is private. No AWS, OpenAI or other model-provider account is needed for the shipped synthetic flows.

Check Python and Git before proceeding:

**Windows PowerShell**

```powershell
py -3.11 --version
git --version
```

**Linux/macOS terminal**

```bash
python3 --version
git --version
```

If your only installed Python is 3.12, use `py -3.12` on Windows or a Python 3.12 interpreter on Linux/macOS. If Git, Python or repository credentials are missing, install/authorise those prerequisites first. Those prerequisites cannot be supplied by AEA itself.

### 0.2 First checkout and install

Run one matching block. The **commands deliberately target `dev`**, not `master`.

**Windows PowerShell:**

```powershell
git clone --branch dev https://github.com/AdityaSreevatsaK/agent-engineering-accelerator.git
Set-Location agent-engineering-accelerator
py -3.11 -m pip install uv==0.10.0
uv --version
uv lock --check
uv sync --python 3.11 --all-extras --group dev --locked
uv run --locked aea --help
```

**Linux/macOS:**

```bash
git clone --branch dev https://github.com/AdityaSreevatsaK/agent-engineering-accelerator.git
cd agent-engineering-accelerator
python3 -m pip install 'uv==0.10.0'
uv --version
uv lock --check
uv sync --python 3.11 --all-extras --group dev --locked
uv run --locked aea --help
```

**Expected:** `uv --version` reports `uv 0.10.0`; `uv lock --check` exits 0; `aea --help` lists `init`, `doctor`, `run`, `check`, `compare`, `report`, `export` and `backups`. Stop and resolve failed installation before proceeding. The lockfile must not be upgraded just to bypass a failed check.

**Existing checkout:** Enter that folder, verify `git branch --show-current` reports `dev`, then run `git pull --ff-only`, `uv lock --check` and `uv sync --all-extras --group dev --locked`. Do not reset or discard uncommitted work. All following commands expect you to be back at the repository root.

## A. Run a complete leadership demonstration

**From the repository root:**

```sh
uv run --locked python scripts/leadership_demo.py --output-dir demo-evidence-001
```

**Expected:** Final output says `PASS: synthetic AEA demonstration`, 11/11 baseline, passing unchanged check, regression detected and HTML produced. The script already performs all stages and handles the intentionally non-zero regression result correctly.

**Read these outputs in order:**

1. `demo-evidence-001/DEMO.md`: what passed/failed and presenter talking points.
2. `demo-evidence-001/regression-report.html`: open in a browser to see the case-level regression.
3. `demo-evidence-001/evidence.json`: structured synthetic evidence.
4. `docs/DEMO.md`: exact five-minute presentation script.

The directory also contains baseline and run logs. Do not upload those files without reviewing identifiers and metadata. **This demo is not independent adoption or real-customer validation.**

## B. Full AWS Strands equipment warranty flow

The standalone example contains its own `agent.py`, `dataset.jsonl` with **12 cases**, and `aea.toml`. There are no AWS calls: it uses a deterministic Strands model double.

**Windows PowerShell:**

```powershell
# Starting at the AEA repository root
Set-Location integrations/equipment_strands

# 1. Verify the cases and Python factory without evaluating an agent
uv run --locked aea doctor dataset.jsonl --config aea.toml

# 2. Create the first approved reference snapshot
uv run --locked aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline

# 3. Run the same good agent against the approved reference
uv run --locked aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1

# 4. Introduce the supplied bad factory without editing application code
uv run --locked aea check dataset.jsonl --config aea.toml --agent agent:build_broken_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
if ($LASTEXITCODE -ne 1) { throw 'Expected a regression quality-gate exit code of 1' }

# 5. Inspect retained versions (read-only), then go back to the root
uv run --locked aea backups runs/approved
Set-Location ../..
```

**Linux/macOS:** Use `cd integrations/equipment_strands` instead of `Set-Location`. Steps 1 to 3 and 5 use the **same** `uv run --locked aea ...` commands. For step 4, run:

```bash
uv run --locked aea check dataset.jsonl --config aea.toml --agent agent:build_broken_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
test "$?" -eq 1 || { echo "Expected regression exit 1"; exit 1; }
cd ../..
```

**Expected:** Doctor reports `PASS: preflight complete`; baseline and unchanged check report `passed=12/12`; unchanged check also reports `OK: baseline`; defective factory reports `REGRESSION: baseline` and intentionally exits **1**. This is success for the negative test, not a crash.

Find `comparison.md` beneath the timestamped run folders in `integrations/equipment_strands/runs/evals/`; its `Newly failing` section identifies expired-warranty cases. The approved baseline remains at `integrations/equipment_strands/runs/approved/`.

**Read:** [Strands application details](../integrations/equipment_strands/README.md).

## C. Full LangGraph supplier onboarding flow

This independently structured graph uses custom state, so `aea.toml` includes both `input_map` and `output_map`. The supplier records are synthetic; no cloud access is needed.

**Windows PowerShell:**

```powershell
# Starting at the AEA repository root
Set-Location integrations/vendor_langgraph
uv run --locked aea doctor dataset.jsonl --config aea.toml
uv run --locked aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
uv run --locked aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1
uv run --locked aea check dataset.jsonl --config aea.toml --agent agent:build_broken_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
if ($LASTEXITCODE -ne 1) { throw 'Expected a regression quality-gate exit code of 1' }
uv run --locked aea backups runs/approved
Set-Location ../..
```

**Linux/macOS:** `cd integrations/vendor_langgraph`, run the same five AEA commands and use the Bash exit-code check shown in flow B after the deliberately broken command. Return with `cd ../..`.

**Expected:** Doctor passes; the initial and unchanged checks each show 12/12; the faulty graph bypasses sanctions review, triggers `REGRESSION: baseline` and returns **1**. See the timestamped `comparison.md` in `integrations/vendor_langgraph/runs/evals/`. The baseline remains unchanged.

**Read:** [LangGraph application details](../integrations/vendor_langgraph/README.md).

## D. Generate a new agent without editing or cloud credentials

This verifies that the **actual shipped template** can be used without authoring a line of code. Its default `build_agent` factory uses Bedrock; **do not run that factory** for this offline walkthrough. The alternative `build_offline_agent` factory is bundled and deterministic.

**From the repository root, on Windows or Linux/macOS:**

```sh
# 1. Create a fresh starter from the installed package
uv run --locked aea init starter_agent

# 2. Validate its 5 predefined cases and no-credential Strands factory
uv run --locked aea doctor starter_agent/dataset.jsonl --adapter strands --agent starter_agent.agent:build_offline_agent

# 3. Freeze a first 5-case baseline
uv run --locked aea check starter_agent/dataset.jsonl --adapter strands --agent starter_agent.agent:build_offline_agent --baseline starter_baseline --runs-dir starter_runs --max-samples 1 --update-baseline

# 4. Evaluate the unchanged starter
uv run --locked aea check starter_agent/dataset.jsonl --adapter strands --agent starter_agent.agent:build_offline_agent --baseline starter_baseline --runs-dir starter_runs --max-samples 1

# 5. Print its completed Markdown report
uv run --locked aea report starter_baseline

# 6. Generate a standalone HTML copy without needing a browser for conversion
uv run --locked aea export starter_baseline/report.md --format html --output starter_report.html

# 7. Inspect retained baseline copies without changing them
uv run --locked aea backups starter_baseline
```

**Expected:** `starter_agent/agent.py` and `dataset.jsonl` appear; doctor reports five valid cases; both checks report `passed=5/5`; comparison reports `OK: baseline`; `starter_report.html` exists in the repository root; `backups` reports no prior versions on the first freeze. A dedicated automated release check runs this exact flow from a disposable folder with provider credentials cleared:

```sh
uv run --locked python scripts/verify_starter_walkthrough.py
```

For real use, replace the *generated* factory, tools, model and JSONL cases with the ones from your application, then follow flow I. Never expose production credentials in code or CI.

## E. Run unit, integration, privacy and package checks

From the repository root, run in order:

```sh
uv lock --check
uv run --locked ruff check src examples
uv run --locked pyright
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/run_checks.py --slow
uv run --locked python scripts/check_examples.py
uv run --locked python scripts/verify_regression_gate.py
uv run --locked python scripts/check_privacy_e2e.py
uv run --locked python scripts/validate_independent_integrations.py --repeats 1
uv run --locked python scripts/verify_starter_walkthrough.py
uv build --wheel
uv run --locked python scripts/check_distribution.py
```

**Expected:** All commands exit 0. The test runner prints its passing-test count. The deliberate defect inside `verify_regression_gate.py` is internally handled, so the script itself returns 0 when detection worked. The wheel check uses an isolated virtual environment and prints `PASS: built wheel`.

**Full CI:** A pull request targeting `dev` starts GitHub Actions automatically; all Windows/Linux Python 3.11/3.12 jobs, full examples, slow acceptance and fresh-install onboarding must be green. **Do not merge into `master` to trigger CI.** Detailed checks: [test guide](TESTING.md).

## F. Run both frameworks and a repeated regression pilot

**Automated standalone applications:** From the repository root:

```sh
uv run --locked python scripts/validate_independent_integrations.py --repeats 2 --output-dir integration-evidence-001
```

**Expected:** Both 12-case applications freeze passing references, pass two unchanged checks, detect deliberately injected faults, and preserve baseline bytes. Read `integration-evidence-001/evidence.json`. This is technical cross-framework validation.

**Separate two-adapter calculator rehearsal:**

```sh
uv run --locked python scripts/pilot_rehearsal.py --output-dir pilot-rehearsal-001 --repeats 3
```

**Expected:** Strands and LangGraph each pass a 10-case baseline, three unchanged comparisons and one intentionally detected defect. Read `pilot-rehearsal-001/REHEARSAL.md` followed by `evidence.json`.

These two workflows are **self-authored synthetic tests, not two independent delivery teams**. Use the [human pilot protocol](HUMAN_EFFORT_STUDY.md) only when a real engineer is available.

## G. Compare AEA with native QA and measure runtime

**Synthetic AEA runtime benchmark:**

```sh
uv run --locked python -m scripts.benchmark_agent_evaluations --repeats 3 --output-dir benchmark-evidence-001
```

Read `benchmark-evidence-001/BENCHMARK.md` and `evidence.json`.

**AEA versus a minimal, direct-framework control:**

```sh
uv run --locked python -m scripts.controlled_pilot_study --repeats 3 --output-dir controlled-pilot-001
```

Read `controlled-pilot-001/STUDY.md` and `evidence.json`. Expected: both methods pass the same 12 cases and agree on **five** failing equipment cases and **three** failing supplier cases. AEA baseline bytes remain unchanged.

**What the numbers do not mean:** The control does not produce AEA-equivalent traces, full scores, retained baseline or reporting. Do not compare raw subprocess times as a developer-productivity percentage. See [measurement methodology](BENCHMARKING.md).

## H. Measure scripted onboarding and review the results

**From the repository root, in the already-installed environment:**

```sh
uv run --locked python -m scripts.onboarding_rehearsal --skip-install --output-dir onboarding-evidence-001
```

This measures `aea doctor`, the first 12-case AEA report, unchanged comparison, deliberate fault and the minimal native control for each application. It **does not** measure dependency installation when `--skip-install` is used.

**To include dependency sync (the uv tool must be available on PATH):**

```sh
python -m scripts.onboarding_rehearsal --output-dir onboarding-evidence-with-install-001
```

This measures a locked dependency sync on the running machine, which may benefit from installed files and package caches. The dedicated CI `Fresh-environment scripted onboarding measurement` uses a previously unpopulated project environment on a new runner and retains only the safe summary files for 14 days.

**Expected:** Read `ONBOARDING_REHEARSAL.md` and `evidence.json` in the selected output directory. Normal cases pass; five Strands and three LangGraph controlled failures agree with the direct control; all human work-time fields remain `null`. The script cannot measure how long somebody takes to learn, adapt or debug a real workflow.

## I. Connect an existing application to AEA

**This is the only integration flow that cannot run without external application code.** Do not invent a factory, a customer dataset, provider access or permissions. The following is the complete implementation procedure once the existing agent is available.

1. In that application's own Python module, expose a no-argument `build_agent()` function that returns a **fresh Strands agent** or **compiled LangGraph graph**. Each test attempt must get an independent instance. Keep credentials and provider configuration in the application's approved environment, never in source.
2. Create a JSONL dataset with at least one object per line, including unique `id`, `input` and expected result. Example synthetic case:

   ```json
   {"id":"case-001","input":"Explain the sample request","expected_output":"Sample answer"}
   ```

3. In that application's directory create `aea.toml` with the appropriate content. **Strands:**

   ```toml
   adapter = "strands"
   agent = "agent:build_agent"
   ```

   **LangGraph custom state:**

   ```toml
   adapter = "langgraph"
   agent = "agent:build_agent"
   input_map = "agent:to_request"
   output_map = "agent:read_decision"
   ```

   The mapper names must refer to **actual trusted callable functions** that translate between case inputs and graph state. For a conventional `messages`-state graph, mappers may be unnecessary.
4. Install the application and AEA into a compatible local Python environment. **Run from the application's working directory**, where `agent:build_agent` imports successfully, then execute:

   ```sh
   aea doctor dataset.jsonl --config aea.toml
   aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
   aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1
   ```

5. Introduce a known defect in a separate disposable application branch/factory. Run `aea check` again with `--agent agent:your_broken_factory` and verify the expected regression exit 1 and the exact failing case IDs. Review the `comparison.md` and baseline fingerprints.
6. Add the same approved offline check to the application's PR pipeline and record a technical reviewer. No live-model payments or sensitive captured inputs without approval. Use [the pilot acceptance checklist](PILOT.md) and [blank engineer timecard](HUMAN_EFFORT_STUDY.md).

**Note:** The `aea` shell command in this section assumes AEA is installed in the application's activated environment. For flows A to H the reproducible `uv run --locked` commands are run inside AEA's checkout instead.

## J. Inspect backups, recovery and release gates

**Read-only backup inventory** (example after flow D):

```sh
uv run --locked aea backups starter_baseline
```

On the very first baseline freeze, the expected result is `No retained AEA baseline backups found`. After an intentional later update, old snapshots are retained in sibling hidden backup folders. **Never blindly delete hidden backups or lock files.**

**If interrupted during an update:** Stop new writers, confirm the owning process is no longer running, identify the backup with `aea backups`, and follow [the manual recovery procedure](OPERATIONAL_READINESS.md). The tool does not automatically restore previous snapshots. Restoration and lock cleanup require an authorised operator's judgment.

**Security and adoption:** [Issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) remains open. The [release checklist](RELEASE_CANDIDATE_CHECKLIST.md) and [human effort timecard](HUMAN_EFFORT_STUDY.md) distinguish green CI from genuine delivery-team adoption, handling of sensitive data and release-owner approval. **Do not promote or tag `master` without explicit permission.**

## Troubleshooting and interpretation

| Symptom | Exact next step |
| --- | --- |
| `uv` is not recognised | Confirm `uv 0.10.0` was installed to a scripts directory on PATH; restart the terminal and rerun `uv --version` |
| Private repository clone fails | Authenticate Git to the authorised GitHub account; do not use someone else's credentials |
| `uv lock --check` fails | Confirm branch is `dev` and the checkout is clean; do not silently regenerate the lockfile |
| Factory cannot be imported | Run inside the *application* directory for `agent:build_agent`, or use the full importable dotted module name from the AEA root |
| Custom LangGraph input/output error | Check that `aea.toml` defines actual `input_map`/`output_map` functions matching the application's state |
| `aea doctor` passes, then evaluation fails | Doctor imports trusted modules but does **not** construct agents, call models or verify graph-state compatibility; read the runtime error |
| `aea check` returns 1 with `REGRESSION` | An intentional broken-agent test succeeded. For an unexpected regression, inspect `comparison.md` and stop the change |
| `aea check` returns 2 | Configuration or run failure. Inspect the command's stderr and the selected dataset/factory |
| `--output-dir` already exists | Use another fresh name, e.g. `demo-evidence-002`; do not overwrite prior data |
| HTML conversion works but PDF does not | PDF export needs local Edge/Chrome/Chromium. HTML export is the no-browser-conversion fallback |
| CLI run finishes but some test cases fail | `aea run` completing is not a quality gate; use `aea check` to evaluate regressions |
| Generated reports contain sensitive identifiers | Do not share them. Default redaction can still retain case IDs, file paths, tool/model names and trace metadata |

### Completion criteria

For **each** supported synthetic application: doctor succeeds, expected normal cases pass, one unchanged check is clean, planted faults are detected with their exact case IDs, approved baseline remains unchanged and expected report artefacts exist. The release CI additionally verifies the generated offline starter, package installation and the seven-job Windows/Linux acceptance.

For a **real existing application**, add independent engineering effort observations and authorised data/security review. Automated synthetic proofs do not satisfy those external requirements.

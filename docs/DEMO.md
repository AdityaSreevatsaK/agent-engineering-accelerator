# AEA: five-minute leadership demonstration

**Audience:** Engineering leadership assessing a reusable evaluation component.  
**Decision at end:** Whether to approve a measured, two-framework synthetic pilot. **Not** a production or release approval.

## Rehearse before the meeting

From the repository root, in an environment with Python 3.11 and uv:

```sh
uv lock --check
uv sync --all-extras --group dev --locked
uv run --locked python scripts/leadership_demo.py --output-dir demo-output
```

The output directory **must be unused**. If it already exists, choose a new one; the runner refuses to overwrite. The demo needs no cloud credentials, performs no billable model requests and uses synthetic Orders data.

**Open for presentation:** `demo-output/DEMO.md` (briefing), `demo-output/regression-report.html` (rendered failure comparison), and `demo-output/evidence.json` (structured result). Keep `demo-output/runs/` and `demo-output/baseline/` local; default redaction can still retain identifying metadata.

For a separate evidence view, open [two standalone application integrations](../integrations/README.md). The Strands equipment-support and LangGraph supplier-onboarding apps each pass 12 synthetic cases and detect one planted fault. They are independent application *designs*, not adopters from different teams.

## Exact five-minute script

| Clock | Presenter action | What to say |
| --- | --- | --- |
| **0:00–0:45** | Show the [showcase architecture](LEADERSHIP_SHOWCASE.md) | “Agents evolve. Their prompts, tools and business rules can drift. AEA gives teams a repeatable external quality gate without imposing one orchestration framework.” |
| **0:45–1:30** | Open `examples/orders/dataset.jsonl` and `examples/orders/agent.py` | “Teams bring an existing factory and a JSONL set of expected outcomes. The evaluation toolkit handles running, scoring, tracing, comparing and reporting.” |
| **1:30–2:30** | Show `demo-output/DEMO.md` with the 11/11 baseline and clean second check | “We establish a baseline and repeat the approved behaviour. Both complete, and the clean check exits zero.” |
| **2:30–4:00** | Open `demo-output/regression-report.html` and find the newly failing refund case | “The deliberately defective refund-policy implementation triggers the regression gate with exit code 1 and identifies an actionable failing case. The original baseline stays unchanged.” |
| **4:00–5:00** | Show [value scorecard](VALUE_ASSESSMENT.md), the [CI run](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43610474918) and [pilot worksheet](PILOT_EVIDENCE_TEMPLATE.md) | “Two frameworks work in synthetic CI. We have concrete test and runtime evidence, but have not yet measured engineer-hours saved, live provider behaviour or independent team adoption. The request is a controlled pilot.” |

### Explanation of the statuses

The **Orders** demo has 11 synthetic cases, separate from the two 12-case standalone integrations. The script asserts a passing reference, a passing unchanged run, an intentional `REGRESSION` with exit 1, a case-level refund failure and unchanged baseline hashes. It also exports a standalone HTML comparison.

**Important API distinction:** `aea run` can return exit 0 when an evaluation finishes even if some scored cases fail. The `aea check` / `aea compare` quality gate is what returns exit 1 for a detected regression. Do not describe ordinary `run` exit 0 as proof that every evaluated case passed.

### Optional technical follow-up after the five-minute demo

```sh
uv run --locked python scripts/validate_independent_integrations.py --repeats 1
uv run --locked python -m scripts.benchmark_agent_evaluations --repeats 3 --output-dir new-benchmark-folder
uv run --locked python scripts/dependency_inventory.py
```

Each command uses synthetic data. The benchmark's `BENCHMARK.md` measures wall-clock CLI runs, not engineering productivity. The dependency inventory checks locked source origins and artefact hashes; it does not scan CVEs or licences.

## Decision, objections and boundaries

A defensible leadership claim is **“A working local cross-framework evaluation contract with CI-tested regression detection”**.

Do **not** claim measured time saved, production security approval, universal model-provider coverage or adoption by independent teams. These need separately approved proof.

For the requested next action, obtain a security-approved **synthetic** pilot with independent Strands and LangGraph engineers, comparable control tasks, elapsed-time measurements and recorded outcomes. Use the [benchmark protocol](BENCHMARKING.md) and deliberately [blank pilot evidence template](PILOT_EVIDENCE_TEMPLATE.md).

**Handling:** Run trusted agent code only. Review report filenames, case IDs, model/tool names, paths and trace metadata before presenting outside the team. Do not commit demo outputs, credentials, client material or sensitive pilot outcomes.

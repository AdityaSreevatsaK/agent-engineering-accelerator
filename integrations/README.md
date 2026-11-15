# Standalone AEA integration examples

**Start-to-finish commands, including expected intentional-regression exit codes:** [Full step-by-step AEA workflows](../docs/STEP_BY_STEP.md#b-full-aws-strands-equipment-warranty-flow). Follow the adjacent LangGraph flow for its custom-state mapper setup. Neither requires editing code or cloud credentials.


Two applications exercise only AEA's installed **public CLI** from their own working directories. Neither imports AEA internals or the other application.

| Application | Framework | Unique integration boundary | Deliberate defect |
| --- | --- | --- | --- |
| [Equipment warranty](equipment_strands/README.md) | Strands | Two-tool Strands workflow including failed lookups | Expired warranty treated as covered |
| [Supplier onboarding](vendor_langgraph/README.md) | LangGraph | Non-messages custom state with input/output mapping | Sanctions review bypassed |

Each has its own 12-case `dataset.jsonl` and **ready-to-run `aea.toml`**, avoiding the need to repeat long adapter and mapping options.

## One-command individual flows

From the AEA checkout after installation, use either command with an **unused** folder name:

```sh
uv run --locked python scripts/validate_independent_integrations.py --only equipment-strands --repeats 1 --output-dir strands-001
uv run --locked python scripts/validate_independent_integrations.py --only vendor-langgraph --repeats 1 --output-dir langgraph-001
```

Each command automatically freezes a baseline, verifies 12 cases, detects a known defect and checks that the baseline is intact. See the [simple PowerShell guide](../docs/STEP_BY_STEP.md) to run or read the outputs.

## Automated acceptance

After `uv sync --all-extras --group dev --locked` from the AEA repository root:

```sh
uv run --locked python scripts/validate_independent_integrations.py --repeats 2
```

The script runs from each application's directory, freezes a baseline, checks unchanged behaviour, introduces a defect and verifies both regression detection and unchanged baseline bytes. It uses synthetic data and local deterministic model doubles, with no provider credentials or billable calls. Pass `--output-dir new-path` to retain a report; an existing output directory will not be overwritten.

For direct CLI use and troubleshooting, follow the application-specific guides. The `--agent` flag overrides the factory in `aea.toml`; mapping functions remain configured.

**Evidence boundary:** both integrations were authored as part of this validation. They are not independent external-team adoption, production provider tests, or security certification.

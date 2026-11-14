# AEA standalone integration validation

Two deliberately **separate application projects** exercise only the published `aea` CLI. Neither imports any `agent_accelerator` implementation modules or imports the other application.

| App | Framework | What it exercises | Controlled defect |
| --- | --- | --- | --- |
| [Equipment warranty](equipment_strands/README.md) | AWS Strands | Real tool execution, two-step lookup, tool failures and tool-call assertions | Expired warranties incorrectly become covered |
| [Supplier onboarding](vendor_langgraph/README.md) | LangGraph | Custom TypedDict state, routing decisions and both input/output mapping hooks | Sanctions screening silently bypassed |

Both use synthetic records and deterministic model doubles, with no paid API requests, credentials, databases or network service required.

From the AEA repository root, after `uv sync --all-extras --group dev --locked`:

```sh
uv run --locked python scripts/validate_independent_integrations.py --repeats 2
```

The command changes into each standalone application directory, freezes separate baselines, verifies identical runs, injects a defect, checks non-zero regression status and compares baseline file digests. An optional `--output-dir new-folder` retains evidence; do not select an existing folder. Inputs and model/tool payloads are redacted by default, but case names, paths and metadata still require review before sharing.

**Scope boundary:** these applications were authored for validation, not contributed by unrelated teams. A successful local run is technical evidence only, not proof of adoption or a production security clearance.

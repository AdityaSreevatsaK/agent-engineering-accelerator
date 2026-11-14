# AEA v2.2.0: developer experience and standalone integration audit

**Date:** 14 November 2026  
**Scope:** Two independently structured but self-authored synthetic projects; published `aea` CLI used from each application directory. This is technical validation, not a usability study involving other engineers.

## Evidence

[Integration validation PR #113](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/113) was merged to `dev` after [6/6 CI jobs passed](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43586061939), including a release job that ran the following **from separate application directories**:

| Integration | Independent app contract | Actual synthetic CI result |
| --- | --- | --- |
| Strands equipment warranty | Two tool calls, expired/valid assets, missing equipment and missing identifier | All 12 reference cases passed; one unchanged run passed; a faulty expiry policy caused CLI regression exit 1; baseline bytes unchanged |
| LangGraph supplier onboarding | Custom state, decision branching, explicit `input_map` and `output_map` | All 12 reference cases passed; one unchanged run passed; a faulty sanctions policy caused CLI regression exit 1; baseline bytes unchanged |

Neither integration imports AEA's implementation packages. Both use controlled local doubles, not remote model providers. The CI checks do not measure how long a new engineer would take to integrate a real application.

## Onboarding friction and mitigations

| Priority | Finding | Action and remaining limitation |
| --- | --- | --- |
| P1, experience | The direct CLI form repeats framework, agent, baseline and mapping parameters across three runs; a LangGraph custom-state invocation is especially long | Added one ready-to-run `aea.toml` per standalone app; the good/broken comparison still uses documented `--agent` override |
| P1, documentation | `module:function` imports resolve relative to the process's working directory, not the location of a config file | Both guides specify activation from the root and execution from the application directory; the end-to-end script enforces this boundary |
| P2, correctness | A custom-state LangGraph requires both an input translator and an output translator, which can be overlooked | The example `aea.toml` explicitly sets both. Broader preflight validation and diagnostics for absent maps are still candidates for a future improvement |
| P2, safety | An `aea check --update-baseline` action creates files and backups, and default redaction retains some identifying metadata | All walkthroughs keep baselines under ignored `runs/`; explain backup retention and non-anonymous metadata before internal use |
| P2, proof | Project-authored demonstrations cannot demonstrate independent developer productivity or two-team adoption | Keep [the independent pilot evidence template](PILOT_EVIDENCE_TEMPLATE.md) blank and [issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) open |

## Reproducible start-to-finish pathway

1. Run `uv sync --all-extras --group dev --locked` at the AEA root, then activate the virtual environment.
2. Enter either `integrations/equipment_strands` or `integrations/vendor_langgraph`.
3. Run `aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline`.
4. Run the same command without `--update-baseline`. Verify no regression and exit code 0.
5. Add `--agent agent:build_broken_agent` when checking again. Verify exit code 1, case-level explanations, and unchanged approved baseline.
6. For fully automated offline checks from the root, use `uv run --locked python scripts/validate_independent_integrations.py --repeats 2`.

**Important:** the script itself measures pass/fail and baseline integrity, not human elapsed onboarding time. No claims of time saved or team adoption are supported yet.

## Remaining engineering checks

- Test the configured onboarding flow in fresh CI after introducing the TOML files, without paid models.
- Run the integration acceptance matrix after future AEA packaging or adapter changes.
- Reference syntax and missing-module errors are now checked with focused unit tests; missing LangGraph mapping hooks on custom-state graphs remain a separate preflight/diagnostic improvement candidate.
- Exercise the partially selected CLI integration cases, marked-slow pathways and independent dependency/security review separately.
- Only a real team and an authorised security reviewer can supply actual rollout and confidential data approval evidence.

**Decision:** Appropriate for additional controlled synthetic engineering validation; not approved for customer production data, organisational roll-out or promotion of `master`.

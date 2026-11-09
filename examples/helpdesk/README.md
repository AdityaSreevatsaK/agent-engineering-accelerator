# IT helpdesk, supervisor plus approval gate (LangGraph)

A supervisor hands each IT request to one of two worker subgraphs: diagnostics checks a device, actions resets passwords and handles admin access. Admin access goes through an approval gate: after `request_approval` the graph pauses with `interrupt()` for the approver, so the run ends interrupted and `grant_admin_access` is never called without approval. The demo shows a graph refactor that drops the gate, caught by `aea check`.

**The model is simulated.** `SimulatedHelpdeskModel` is a deterministic rule engine, not an LLM, so the demo is reproducible offline without credentials or cost. It reads the system prompt it receives and applies only the rules that prompt states (`*_SENTENCES` in `rules.py`); the prompt's first sentence names the role, so one double plays the supervisor and both workers. The gate is not a rule of the double: the actions prompt says the workflow pauses after `request_approval`, so the model calls `grant_admin_access` as soon as `request_approval` returns, and only the graph stands between the two. Everything else is real: the supervisor's handoff `Command`s, the worker subgraphs, `ToolNode`, `interrupt()`, the `InMemorySaver` checkpointer and the tool errors.

## Shape

- `supervisor` (root): bound to `transfer_to_diagnostics` and `transfer_to_actions`; a handoff is a `Command` to the worker node plus a `ToolMessage` answering the call. Anything that is not an IT request is declined with no tool call.
- `diagnostics` (subgraph): `check_device_status(device_id)`; reports online or offline, last seen, and a low disk warning under 10% free.
- `actions` (subgraph): `reset_password(username)`, `request_approval(username, device_id)`, `grant_admin_access(username, device_id)`, and the `approval_gate` node after `request_approval`.
- Workers answer the user directly and end the run. Unknown devices and users raise in the tool and come back to the model as tool errors.
- The handoff tool calls are recorded at the root and the worker tool calls inside the subgraphs, so the trajectory checks prove the adapter collects tool calls from every namespace.

## Files

- `agent.py`: the graph, the model double, `build_agent` (gated), `build_ungated_agent` (the refactor) and `build_live_agent` (Bedrock).
- `rules.py`: the device and user directory, tool logic, the three prompts and the rule engine.
- `dataset.jsonl`: 10 cases: four diagnostics (including an unknown device and a missing device ID), two password resets (one unknown user), two admin access requests, two out of scope. Every case checks the trajectory: which team was called, the tool arguments, forbidden tools, a tool-call budget, and `expect_interrupt`.
- `golden.jsonl`: reference answers for six non-interrupt cases (five with a human `label`), for the LLM judge demo. An interrupted case has no answer to judge.

The two admin access cases (`admin_local_docker`, `admin_driver_update`) set `expect_interrupt: true` and have no answer checks, because an interrupted run's answer is empty.

## Demo

`build_ungated_agent` is the same agent after a plausible refactor: the actions worker's conditional edge from `tools` to `approval_gate` was replaced by the standard `tools -> model` edge, so nothing pauses between `request_approval` and `grant_admin_access`. Model, prompts and tools are unchanged.

```sh
# Shared flags for every step
CHECK="uv run aea check examples/helpdesk/dataset.jsonl --adapter langgraph --baseline baselines/helpdesk"
```

1. Freeze the good agent as the baseline (10/10, exit 0):
   `$CHECK --agent examples.helpdesk.agent:build_agent --update-baseline`
2. Make the refactor by switching the factory: `--agent examples.helpdesk.agent:build_ungated_agent`.
3. Check it. It exits 1 with `REGRESSION` and lists the failing cases:
   `$CHECK --agent examples.helpdesk.agent:build_ungated_agent`
   - `admin_local_docker`: `grant_admin_access` is called (forbidden), no interrupt (expected an interrupt), 3 tool calls over a budget of 2.
   - `admin_driver_update`: the same three failures for a second user and device.
4. Inspect the report: open the `comparison:` path it prints (`runs/<run-id>/comparison.md`) for the newly failing cases and checks, and `runs/<run-id>/report.md` for the per-case trace summary.
5. Revert by switching back to `build_agent`. It exits 0 with `OK`:
   `$CHECK --agent examples.helpdesk.agent:build_agent`

The other eight cases pass under both agents, and the ungated agent's answer ("Admin access on LT-2001 has been granted to bchen.") reads as a success: the regression is visible only in the trajectory and the missing interrupt, which is why answer checks alone miss it. Step 1 rewrites `baselines/helpdesk/` with new run ids; restore it with `git checkout baselines/helpdesk` if you do not want the change.

## LLM judge demo (offline)

```sh
RUN="uv run aea run examples/helpdesk/dataset.jsonl --adapter langgraph --judge mockllm/aea-judge-double"
```

1. Golden, calibration: `$RUN --golden examples/helpdesk/golden.jsonl --agent examples.helpdesk.agent:build_agent`. The six golden cases are judged against their reference, the rest reference-free; the report's Judge section shows agreement with human labels 5/5. The two admin cases end interrupted, so the judge does not judge them (`not judged: interrupted`) and `expect_interrupt` decides them.
2. Golden, regression: the same command with `--agent examples.helpdesk.agent:build_ungated_agent`. The golden answers are unchanged, because no golden case touches the gate, so agreement stays 5/5. The two admin cases fail on the dataset checks, not the judge: a judge reads answers, and this regression changes what the agent did, not what it said.

## Live model

`--agent examples.helpdesk.agent:build_live_agent` runs the gated graph on `ChatBedrockConverse` with `us.anthropic.claude-haiku-5-5`. It needs `langchain-aws` installed and AWS credentials; the import is inside the factory, so the offline factories do not need it.

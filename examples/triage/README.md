# Support-ticket triage (LangGraph, custom state)

An agent that triages a customer support ticket: a classifier node picks a category and priority, and conditional edges route the ticket to a billing, technical or general specialist, which may call a tool and writes the reply. The answer is JSON with `category`, `priority` and `reply`. The demo shows a reworded classifier prompt causing a regression, caught by `aea check`.

**The graph has no `messages` channel.** Its state is a custom `TypedDict` (`message`, `category`, `priority`, `reply`), so aea needs the mapping hooks: `--input-map examples.triage.agent:to_input` turns the case input into `{"message": ...}`, and `--output-map examples.triage.agent:from_output` turns the final state into the JSON answer. Tool calls are recorded in a separate `trail` channel (an `AIMessage` with the tool call, then its `ToolMessage`), so they appear in the graph's update events and in the trajectory.

**The classifier is simulated.** `SimulatedTriageModel` is a deterministic rule engine, not an LLM, so the demo is reproducible offline without credentials or cost. It reads the classifier prompt it receives and applies only the routing rules that prompt states: each rule is one sentence (`RULES` in `rules.py`), tried in the order the prompt states them, first match wins. Reword or reorder the prompt and the routing changes, which is the failure a real model shows when an instruction is edited away. The specialists, tools and graph are real.

## Policy

- A billing ticket that reports a duplicate charge, or comes from an angry customer, is high priority and escalated to a human.
- A technical ticket that reports an outage is high priority (not escalated: it matches the outage known issue).
- Invoices, refunds, payments and charges are billing; errors, crashes, bugs, slowness and login problems are technical; passwords, profile details and closing an account are account; anything else is other, low priority.
- Billing looks up the invoice named in the ticket (`INV-` number) or asks for it; technical searches the known issues; account and other get a self-service answer with no tool.

Tools: `lookup_invoice(invoice_id)`, `search_known_issues(query)`, `escalate_to_human(queue, priority, summary)`, all over in-memory data in `rules.py`.

## Files

- `agent.py`: the graph, the classifier double, the mapping hooks `to_input` and `from_output`, `build_agent` (`PROMPT`), `build_reworded_agent` (`PROMPT_REWORDED`) and `build_live_agent` (Bedrock).
- `rules.py`: invoices, known issues, tool logic, both prompts and the routing rules.
- `dataset.jsonl`: 12 cases, at least one per route and priority. Every case checks the JSON fields (`category` and `priority` exactly) and the trajectory: which tools are called, which are forbidden, their arguments where they matter, and a tool-call budget.
- `golden.jsonl`: reference answers for six of the twelve cases (five with a human `label`), for the LLM judge demo, including the planted `charged_twice_furious` reply.

## Demo

`PROMPT_REWORDED` is a plausible tidy-up: shorter, technical listed first and broadened to cover "something that happened twice", and the urgent-billing sentence folded away.

```sh
# Shared flags for every step: aea.toml sets the adapter, agent and maps; --agent on the command line overrides it.
CHECK="uv run aea check examples/triage/dataset.jsonl --config examples/triage/aea.toml --baseline baselines/triage"
# The same without the config file, with every flag spelt out:
# CHECK="uv run aea check examples/triage/dataset.jsonl --adapter langgraph --input-map examples.triage.agent:to_input --output-map examples.triage.agent:from_output --baseline baselines/triage"
```

1. Freeze the good agent as the baseline (12/12, exit 0):
   `$CHECK --agent examples.triage.agent:build_agent --update-baseline`
2. Make the prompt change by switching the factory to the reworded prompt: `--agent examples.triage.agent:build_reworded_agent`.
3. Check it. It exits 1 with `REGRESSION` and lists the failing cases:
   `$CHECK --agent examples.triage.agent:build_reworded_agent`
   - `charged_twice_furious`: "I was charged twice and I'm furious" is routed to technical, normal priority; `search_known_issues` is called and nobody is escalated.
   - `angry_invoice_dispute`: an angry invoice dispute stays billing but drops to normal priority; the invoice is looked up and nobody is escalated.
4. Inspect the report: open the `comparison:` path it prints (`runs/<run-id>/comparison.md`) for the newly failing cases and the failed checks (`expected_tools`, `forbidden_tools`, the JSON `category` and `priority`), and `runs/<run-id>/report.md` for the per-case trace summary.
5. Revert by switching back to `build_agent`. It exits 0 with `OK`:
   `$CHECK --agent examples.triage.agent:build_agent`

The other ten cases still pass under the reworded prompt, including a plain payment question, an outage and a login problem: the regression is narrow, which is why it is easy to miss by eye. Step 1 creates or rewrites `baselines/triage/`.

## LLM judge demo (offline)

`--judge mockllm/aea-judge-double` adds the `judge` scorer with the deterministic judge double, so no credentials are needed. See the main README's LLM judge section.

```sh
RUN="uv run aea run examples/triage/dataset.jsonl --config examples/triage/aea.toml --judge mockllm/aea-judge-double"
```

1. Golden, calibration: `$RUN --golden examples/triage/golden.jsonl --agent examples.triage.agent:build_agent`. The six golden cases are judged against their reference, the rest reference-free; the report's Judge section shows agreement with the human labels.
2. Golden, regression: the same command with `--agent examples.triage.agent:build_reworded_agent`. The judge fails `charged_twice_furious` too (`golden verdict fail`): the reworded reply is a flat "Logged it for our engineers" instead of an apology and an escalation reference. Calibrate only on the agent version the labels were written for.
3. Swap the double for a real model, for example `--judge bedrock/us.anthropic.claude-haiku-5-5`, to judge the tone of the replies with an LLM (needs AWS credentials).

## Live model

`build_live_agent` runs the good prompt on `ChatBedrockConverse` (`us.anthropic.claude-haiku-5-5`, region from `AWS_REGION` or `AWS_DEFAULT_REGION`, default `us-east-1`). It needs `langchain-aws` installed and AWS credentials. It returns an uncompiled `StateGraph`, which the adapter compiles.

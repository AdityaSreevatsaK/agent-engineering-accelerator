# Expense-claim reviewer (LangGraph)

An agent that reviews a travel expense claim and returns a decision (approve, reject or refer), the approved amount in USD, and one reason per adjusted line. The demo shows a prompt edit causing a regression, caught by `aea check`.

**The model is simulated.** `SimulatedReviewModel` is a deterministic rule engine, not an LLM, so the demo is reproducible offline without credentials or cost. It reads the system prompt it receives and applies only the policy rules that prompt states: each rule is one sentence (`RULE_SENTENCES` in `rules.py`). Drop a sentence from the prompt and the rule silently stops applying, which is the failure a real model shows when an instruction is edited away. Everything else is real: the LangGraph graph, `ToolNode`, the tools and the tool errors.

## Policy

- Alcohol is never reimbursable.
- A line over 75 USD with no receipt is rejected; the threshold applies after conversion (EUR 80 is over, JPY 10,000 is not).
- Meals are capped at the per diem for the trip city and days, in line order.
- Lodging is capped at the nightly limit times the trip days; grade 4 and above use the senior limit.
- A claim over 5,000 USD after conversion is referred, not decided; so is a claim with a currency that cannot be converted.
- Otherwise the claim is approved if anything remains approved, else rejected.

Tools: `lookup_policy(category)` (rule text and limits), `convert_currency(amount, from_currency, to_currency)` (fixed rates in `rules.py`), `per_diem(city, days)`. The double calls them in order: policy per category, conversion per non-USD line, then the per diem when meals are claimed.

## Files

- `agent.py`: the graph, the model double, `build_agent` (`PROMPT`) and `build_condensed_agent` (`PROMPT_CONDENSED`).
- `rules.py`: policy, tool logic, both prompts and the rule engine.
- `dataset.jsonl`: 12 cases, one per decision path and edge case; five involve a non-USD line. Every case also checks the trajectory: policy looked up, `convert_currency` called with each non-USD amount and never for an all-USD claim, `per_diem` with the trip city and days only when meals are claimed, and a tool-call budget.
- `scorers.py`: `amounts_grounded`, which fails any reply whose USD amounts do not trace back to the claim (converted line amounts, their sums, approved amounts within 0..claimed). See its docstring.
- `golden.jsonl`: reference answers for six of the twelve cases (five with a human `label`), for the LLM judge demo.
- `../../baselines/expense/`: the baseline run directory (redacted).

## Demo

`PROMPT_CONDENSED` is a plausible tidy-up: shorter, same tone, every rule kept verbatim except the receipt sentence.

```sh
# Shared flags for every step: aea.toml sets the adapter and agent; --agent on the command line overrides it
CHECK="uv run aea check examples/expense/dataset.jsonl --config examples/expense/aea.toml --scorer examples.expense.scorers:amounts_grounded --baseline baselines/expense"
# The same without the config file:
# CHECK="uv run aea check examples/expense/dataset.jsonl --adapter langgraph --scorer examples.expense.scorers:amounts_grounded --baseline baselines/expense"
```

1. Freeze the good agent as the baseline (12/12, exit 0):
   `$CHECK --agent examples.expense.agent:build_agent --update-baseline`
2. Make the prompt change by switching the factory to the condensed prompt: `--agent examples.expense.agent:build_condensed_agent`.
3. Check it. It exits 1 with `REGRESSION` and lists the failing cases:
   `$CHECK --agent examples.expense.agent:build_condensed_agent`
   - `receipt_missing_over_75`: a 120 USD taxi with no receipt is paid.
   - `receipt_missing_after_conversion`: an EUR 80 (86.40 USD) taxi with no receipt is paid.
   - `reject_no_receipt`: a claim that should be rejected is approved.
4. Inspect the report: open the `comparison:` path it prints (`runs/<run-id>/comparison.md`) for the newly failing cases and the failed checks, and `runs/<run-id>/report.md` for the per-case trace summary.
5. Revert by switching back to `build_agent`. It exits 0 with `OK`:
   `$CHECK --agent examples.expense.agent:build_agent`

The other nine cases still pass under the condensed prompt, including the 75.00 USD boundary and the JPY line that is under the threshold after conversion: the regression is narrow, which is why it is easy to miss by eye. Step 1 rewrites `baselines/expense/` with new run ids; restore it with `git checkout baselines/expense` if you do not want the change.

## LLM judge demo (offline)

`--judge mockllm/aea-judge-double` adds the `judge` scorer with the deterministic judge double, so no credentials are needed. See the main README's LLM judge section.

```sh
RUN="uv run aea run examples/expense/dataset.jsonl --config examples/expense/aea.toml --judge mockllm/aea-judge-double"
```

1. Reference-free (no golden file): every case is judged against the built-in rubric. `$RUN --agent examples.expense.agent:build_agent` passes 12/12, and so does the judge on `build_condensed_agent`: the double only checks the answer is not blank, and even a real judge without references cannot know the receipt rule was dropped. The three failures come from the dataset checks.
2. Golden, calibration: `$RUN --golden examples/expense/golden.jsonl --agent examples.expense.agent:build_agent`. The six cases in `golden.jsonl` are judged against their reference; the other six fall back to reference-free. Each `label` is a human's verdict on the original agent's answer, so this is the run to calibrate the judge on: the report's Judge section shows agreement with human labels 5/5. Cohen's kappa needs at least 10 labelled cases, so it is not printed here.
3. Golden, regression: the same command with `--agent examples.expense.agent:build_condensed_agent`. The judge now fails the three receipt cases too (`golden verdict fail`), so the reference catches what the reference-free judge missed. Agreement drops to 2/5 because the labels describe the original agent's answers, not these: the disagreement on the three receipt cases is the regression, not a judge error. Calibrate only on the agent version the labels were written for.
4. Add `--capture-content` to see the judge's reasons in the log; without it only the mode, verdict and criterion names are stored.
5. Pairwise against a baseline run (no golden file): run the good agent with its answers kept, `$RUN --agent examples.expense.agent:build_agent --capture-content --runs-dir runs/pairwise-baseline` (drop `--judge` here if you like), then `$RUN --agent examples.expense.agent:build_condensed_agent --judge-baseline runs/pairwise-baseline/<run-id>`. The nine unchanged answers are `same`; the three receipt cases differ, and the double's first-shown preference flips when the answers are swapped, so the report counts 3 order disagreements and scores them `same`. A real judge is needed to say which answer is better. Pointing `--judge-baseline` at `baselines/expense` (redacted) exits 2 with an error naming `--capture-content`.

Swap the double for a real model, for example `--judge bedrock/us.anthropic.claude-haiku-5-5`, to judge with an LLM (needs AWS credentials). The judge sees the agent's tool results (policy limits, exchange rates), so figures the agent got from its tools are not marked as unsupported claims.

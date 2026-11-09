# Policy Q&A with agentic RAG (LangGraph)

An agent that answers employee questions about the travel and expense policy by searching a small policy corpus, grading what it retrieved, rewriting the query when nothing relevant came back, and answering with the policy figure and its section id. The demo shows a prompt tweak that skips retrieval and invents a figure, caught by `aea check`.

**The model is simulated.** `SimulatedPolicyModel` is a deterministic rule engine, not an LLM, so the demo is reproducible offline without credentials or cost. It reads the system prompt it receives and applies only the behaviour rules that prompt states: each rule is one sentence (`RULE_SENTENCES` in `rules.py`). It also has its own beliefs (`PRIOR_BELIEFS`), what a model "knows" without searching; the hotel belief is wrong on purpose. Everything else is real: the LangGraph graph, `ToolNode`, the conditional edges and the rewrite loop.

## Graph

- `decide`: the model either calls `search_policy` or answers directly (`tools_condition`).
- `retrieve`: a `ToolNode` running `search_policy(query)`, a keyword search over ten policy chunks, each with a section id such as `TRV-4.2`.
- grade (a conditional edge on `retrieve`): keeps the chunks whose topic terms appear in the query; any left go to `answer`, none go to `rewrite`.
- `rewrite`: drops stopwords and maps everyday words to policy terms (cab to taxi), then back to `decide`. At most 2 rewrites, then `answer`.
- `answer`: the model answers from the graded chunks only, quoting the figure and citing the section id, or says the question is not covered by policy.

Grading and rewriting are plain code in every factory, so only the model's two steps vary between agents.

## Files

- `agent.py`: the graph, the model double, `build_agent` (`PROMPT`), `build_confident_agent` (`PROMPT_CONFIDENT`) and `build_live_agent` (Bedrock).
- `rules.py`: the corpus, search, grader, rewriter, both prompts and the rule engine.
- `dataset.jsonl`: 11 cases. Each requires a `search_policy` call, the exact figure and the section id in the answer, and a tool-call budget. `taxi_query_rewritten` exercises the rewrite loop (its second search must be `expense taxi airport`); `out_of_corpus_pet_boarding` must say "not covered by policy" and cite no section.
- `golden.jsonl`: reference answers for six of the eleven cases (five with a human `label`), for the LLM judge demo. The notes on the two hotel cases describe the faithfulness check: the figure must be the one in `TRV-4.2`.

## Demo

`PROMPT_CONFIDENT` is a plausible latency tweak: it adds "Answer directly when you are confident of the answer." and drops "Always search the policy with search_policy before answering.". Every other sentence is kept verbatim.

```sh
# Shared flags for every step
CHECK="uv run aea check examples/policy_rag/dataset.jsonl --adapter langgraph --baseline baselines/policy_rag"
```

No `--input-map` or `--output-map` is needed: the graph has a `messages` channel and the answer is the last AI message.

1. Freeze the good agent as the baseline (11/11, exit 0):
   `$CHECK --agent examples.policy_rag.agent:build_agent --update-baseline`
2. Make the prompt change by switching the factory to the confident prompt: `--agent examples.policy_rag.agent:build_confident_agent`.
3. Check it. It exits 1 with `REGRESSION` and lists the failing cases:
   `$CHECK --agent examples.policy_rag.agent:build_confident_agent`
   - `hotel_cap_tier1_city`: no search, and the answer is "Hotels are capped at USD 300 per night." with no section id (the policy says USD 250 in London).
   - `hotel_cap_other_city`: the same invented USD 300 for Leeds (the policy says USD 180).
4. Inspect the report: open the `comparison:` path it prints (`runs/<run-id>/comparison.md`) for the newly failing cases and the failed checks (`expected_tools`, `output_contains`, `output_not_contains`), and `runs/<run-id>/report.md` for the per-case trace summary.
5. Revert by switching back to `build_agent`. It exits 0 with `OK`:
   `$CHECK --agent examples.policy_rag.agent:build_agent`

The other nine cases still pass under the confident prompt, including the rewrite loop and the out-of-corpus question: the model only skips retrieval where it believes it already knows the answer, which is why the regression is easy to miss by eye. Step 1 writes `baselines/policy_rag/`; delete it, or restore it with `git checkout baselines/policy_rag` once committed, if you do not want the change.

## LLM judge demo (offline)

`--judge mockllm/aea-judge-double` adds the `judge` scorer with the deterministic judge double, so no credentials are needed. See the main README's LLM judge section.

```sh
RUN="uv run aea run examples/policy_rag/dataset.jsonl --adapter langgraph --judge mockllm/aea-judge-double"
```

1. Golden, calibration: `$RUN --golden examples/policy_rag/golden.jsonl --agent examples.policy_rag.agent:build_agent`. The six cases in `golden.jsonl` are judged against their reference; the report's Judge section shows agreement with human labels 5/5.
2. Golden, regression: the same command with `--agent examples.policy_rag.agent:build_confident_agent`. The judge fails the two hotel cases (`golden verdict fail`): the answer's USD 300 is not supported by the reference. The disagreement with the labels on those two cases is the regression, not a judge error.
3. Add `--capture-content` to see the judge's reasons in the log.

Swap the double for a real model, for example `--judge bedrock/us.anthropic.claude-haiku-5-5`, to judge faithfulness with an LLM (needs AWS credentials). The judge sees the agent's tool results (the retrieved chunks), so figures quoted from them are not marked as unsupported; the confident agent's USD 300 has no tool result behind it.

## Live agent

`--agent examples.policy_rag.agent:build_live_agent` runs the good prompt on `us.anthropic.claude-haiku-5-5` through `ChatBedrockConverse`. It needs `langchain-aws` installed and AWS credentials; it is not part of the offline demo and its answers are not deterministic.

# AEA original Orders example: videos and screenshot recovery

Date: 8 November 2026. Integration branch: `reconstruction/wip-checkpoint-2026-10-30`. `master` unchanged.

## User-provided original evidence

| Historical path | Evidence | Original editor/source dimensions | Candidate |
| --- | --- | --- | --- |
| `examples/orders/rules.py` | complete scrolling screen recording | Unix LF; 156 displayed lines; 6,581 chars | exact counts |
| `examples/orders/agent.py` | complete scrolling screen recording | Unix LF; 109 displayed lines; 3,871 chars | exact counts |
| `examples/orders/dataset.jsonl` | original full Notepad++ screenshot | 11 JSONL entries and final blank line 12 | all 11 entries recovered |

Recovered code candidates have been manually transcribed line-by-line, including original blank lines, type annotations, tools, model double, regexes and refund policy. Both Python files match their editor's **exact line and character counts** and pass AST syntax validation. The dataset fields follow the screenshot, preserving expected tool names/arguments/order, output and JSON-schema checks, forbidden tools and the order of all 11 original case IDs.

## Recovered example behaviour

- In-memory 3-customer and 6-order store with deterministic `find_customer`, `get_order` and `issue_refund` tools.
- Rule-driven multi-turn Strands model double and `Agent` factories `build_agent` and `build_broken_agent`.
- Order status and unknown order cases, latest customer order, customer not found, aggregate spend excluding cancelled orders.
- Refund eligibility restricted to delivered orders within 30 days. `build_broken_agent` deliberately skips this check.
- Structured JSON summary, unknown-scope response, exact tool trajectory and policy-failure assertions.

## Fidelity and CI

Source-verification script pins SHA-256 of the reconstructed candidates, original visible editor dimensions and screenshot case IDs/record count. The new **supplementary** end-to-end verification invokes real AEA CLI and native Strands with no cloud credentials, requiring the good agent to pass all 11 original screenshot cases and the broken agent to fail exactly the two ineligible refund cases (`refund_not_delivered`, `refund_outside_window`).

Dedicated CI checks on Windows/Linux with Python 3.11/3.12 using native `strands-agents`. Passing runtime and editor counts does not establish **byte-for-byte original source identity** because no original source hashes/bytes are available.

Adds **three** original historical paths. After PR merge, original file-path presence increases from 77/117 to 80/117. Additional recordings `tests/unit/test_tracing.py`, `test_tokens.py`, `test_judge_pairwise.py` were supplied in the same user batch and are processed as separate original-source recoveries.

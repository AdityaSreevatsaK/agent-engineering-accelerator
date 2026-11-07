# AEA source-evidence batch 47: triage and expense examples (7 Nov 2026)

**Input evidence:** Two user-supplied Notepad++ TOML screenshots and two user-uploaded WebM videos of the original full agent files. All four sources were inspected in the current reconstruction session. These are original-path candidates; only bytes extracted reliably from screenshots may be called screenshot-matched.

## Restored candidates

| File | Source evidence | Status | Validation |
| --- | --- | --- | --- |
| `examples/triage/aea.toml` | Full 5 populated lines in screenshot; trailing blank line | Transcribed | TOML and reference target AST checks |
| `examples/expense/aea.toml` | Full 3 populated lines in screenshot; trailing blank line | Transcribed | TOML and reference target AST checks |
| `examples/expense/agent.py` | Video start-to-end, Notepad++ Windows CRLF editor shows 4,294 characters, 98 displayed lines | Complete provisional video candidate | 97 LF-terminated source lines; 4,197 normalised LF characters + 97 CRLF extra bytes = **4,294**; AST valid |
| `examples/triage/agent.py` | Video start-to-end, Notepad++ Unix LF editor shows 9,324 characters, 221 displayed lines | **Provisional with unresolved two-character visual mismatch** | 220 LF-terminated source lines -> 221 displayed lines; candidate 9,326 LF characters, **2 more than video counter**; AST valid |

**No undocumented edits to force a character-count match.** The two-character discrepancy in the triage source is explicit and requires line-by-line further evidence review before claiming exact source fidelity. A matching character count does not alone certify byte-level fidelity for expense.

## Confirmed exported entry points

- Triage: `build_agent()`, `build_reworded_agent()`, `build_live_agent()`, `to_input(question)`, and `from_output(state)`; class `SimulatedTriageModel`, source-defined billing/technical/general routes, source-defined tools.
- Expense: `build_agent()` and `build_condensed_agent()`; class `SimulatedReviewModel`, source-defined tools `lookup_policy`, `convert_currency`, `per_diem`.
- Both screenshot configurations select LangGraph and reference declared functions in the agents.

## **Unresolved dependencies and release boundary**

- `examples/triage/rules.py` and `examples/expense/rules.py` remain missing from original historical inventory. Source imports refer to them and runtime agent imports currently fail; cannot safely run original scenario or configuration tests yet. Do not generate stubs or disguise guesses as the historical rules.
- Original triage and expense dataset JSONL and unit tests are also missing; ask user for these as next evidence batch.
- The two configuration-dependent parameterised tests remain **deferred**, pending rules restoration and live callable-reference verification, even though the TOMLs are restored.
- Tests/other file source fidelity and original JSON fixture deferrals are unchanged; existing offline calculator proof is a separate evidence lane.
- No cloud or paid LLM calls. `build_live_agent` is AST-checked only. Never invoke the AWS-backed constructor in CI.
- Historical `master` remains untouched. Merge only after PR branch verification, four-platform source-contract tests, and integrated regression checks all pass.

The source contract audit is `reconstruction_tools/verify_triage_expense_video_candidates.py`; it fails closed on candidate changes but does not claim original-byte equality.

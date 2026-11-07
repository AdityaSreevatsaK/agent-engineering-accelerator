# AEA policy RAG original source reconstruction (Part 58)

Date: 7 November 2026. Target reconstruction/wip-checkpoint-2026-10-30. master untouched.

## User-provided evidence

| Original path | Original evidence | Recorded editor dimensions | Reconstruction dimensions |
| --- | --- | --- | --- |
| examples/policy_rag/rules.py | complete user WebM recording | Windows CRLF, 215 displayed lines, 9,151 characters | 215 displayed lines, 9,151 CRLF-equivalent characters |
| examples/policy_rag/agent.py | complete user WebM recording | LF, 137 displayed lines, 6,147 characters | 137 displayed lines, 6,147 LF characters |
| examples/policy_rag/dataset.jsonl | full screenshot | 11 dataset cases, blank line 12 | 11 cases, blank line 12 |
| examples/policy_rag/golden.jsonl | full screenshot | 6 references, blank line 7 | 6 references, blank line 7 |

All code lines were manually transcribed from overlapping screen-recording frames, including the agent's initial docstring visible shortly after screen-sharing started. Both code files exactly match their original Notepad++ line and character counts. The JSONL files reproduce the visible screenshot fields, values and ordering. Recordings/screenshots do not contain the original file bytes or hashes. Source matching dimensions, executable syntax and runtime semantics are high-confidence candidate evidence but NOT a byte-identity certificate.

## Features recovered

- Original self-contained 10-chunk travel and expense policy corpus with section IDs, keyword ranking, tie order, two-result search limit and deterministic retrieval.
- Query rewrite (cab to taxi) with stopword filtering, graded relevance, a maximum of two rewrites and an explicit not-covered response.
- Prompt-rule model double, tool calls and LangGraph retrieve/grade/rewrite/answer workflow.
- A deliberate prompt regression: build_confident_agent skips retrieval when it believes it already knows the hotel limit, resulting in invented USD 300 rather than the retrieved tier-1/tier-2 limits.
- Lazy optional AWS Bedrock integration in build_live_agent; no credentials needed for offline mode.

## Verification

- Standard-library hash, Python 3.11 AST, original editor count and original screenshot record-order audit.
- Native AEA data schema loader and human golden reference loader validation.
- Reconstructed example E2E tests use the real AEA CLI, native LangGraph and Inspect AI. The good prompt must pass all eleven screenshot cases and exactly match all six golden reference answers; the deliberately confident prompt must fail the two seeded hotel examples, and those replies must contain the unsupported USD 300.
- GitHub Actions matrix: Windows/Linux × Python 3.11/3.12. Offline simulated models only, no paid APIs or credentials.

These checks are supplementary. The original user-recorded tests/unit/test_policy_rag.py remains a separate transcribe-and-review work item. Source entries at the four original paths add 4 to the historical path count only after merging, from 70/117 to 74/117. No master change.

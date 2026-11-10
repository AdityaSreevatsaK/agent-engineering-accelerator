# November 10 source-video fidelity checkpoint — acceptance and security review

**Evidence:** user-provided `docs-acceptance.md.webm` (approx. 26.4s, 1920×1080), `docs-review.md.webm` (approx. 20.3s, 1920×1080).

**Technique:** decoded the newly supplied original recordings, inspected actual video frames across their complete timeline, compared visible editor headings, section order, tables and code references with the committed provisional Markdown. No OCR, byte-identity inference, fabricated historical data or cloud-model calls.

## Result

Both previously requested videos were provided and readable. **No additional recordings of these two documents are presently necessary for semantic reconstruction.**

| Document | Visibly recorded original | Verified coverage in current provisional draft | Historical byte authenticity |
| --- | --- | --- | --- |
| `docs/acceptance.md` | Header, D1–D22 decision table, agreed scope, additions, assumptions, open items, six CLI rows, unit coverage matrix, six deferred rows and end summary; recorded through line 154 | Rechecked matrix structure and restored explicit Fisher p-value caveat; source anchors and version-specific scope documented | Not established; draft remains at `reconstruction_drafts/docs_acceptance_video_PROVISIONAL.md` |
| `docs/review.md` | Dependency/runtime/optional groups, storage and metric types, redaction, six-row retention matrix, security notes, residual risks, known limits; recorded through roughly line 144 | Corrected source section order: 4 Retention and 5 Security notes, plus distinction that report.md excludes raw payloads | Not established; draft remains at `reconstruction_drafts/docs_review_video_PROVISIONAL.md` |

### Evidence anchors

**Acceptance**
- 5–8s: original title, version/date disclaimer and D1–D11 (approx. lines 1–27).
- 11–18s: decisions, agreed scope and LangGraph additions (approx. lines 35–80).
- 19–22s: CLI commands, test coverage matrix (approx. lines 100–134).
- 23–26s: six deferred rows, the available but uncalibrated Fisher `--max-p-value` gate, and the 2.0.0/2.2.0 assessment distinction (lines 137–154).

**Review**
- 7–13s: dependencies, data stored and metric storage (approx. lines 1–65).
- 14–17s: redaction limitations and retention table (approx. lines 67–112).
- 17–20s: security notes, residual risks, final known-limits link (approx. lines 113–144).

## Meaningful corrections

1. Original review places **Retention in §4** and **Security notes in §5**. The previous semantic draft incorrectly reversed their order.
2. Original review explicitly says `report.md` is still a derived summary without raw payloads even for captured runs; the previous draft's wording was ambiguous.
3. Original acceptance §7's live-model-repeatability row mentions an available, uncalibrated `--max-p-value` (Fisher test) gate, not merely absent latency/cost thresholds.
4. The historical coverage matrix's row categories are all present in the provisional draft. Claiming that the entire matrix was missing is now inaccurate; only literal Markdown/source-byte fidelity remains unknown.
5. Original acceptance says the 2.0.0 decision verdict was **not rerun for 2.2.0**. This qualification must be preserved in future release statements.

## Deliberate scope boundary

These are **video-grounded semantic reconstructions, not recovered original Markdown bytes**. Do not install the drafts at `docs/acceptance.md` or `docs/review.md` as if historically authentic; the missing-original inventory stays unchanged. The user also previously confirmed that the historical calculator fixtures are not available, and original uv.lock is not mandatory for new CI.

A modern production release still needs a separate security/retention assessment, explicit approval to replace or waive missing historical artefacts, and release acceptance. Passing current Windows/Linux regression workflows is necessary but not sufficient.

# AEA conformance source recovery (Part 54)

**Date:** 7 November 2026  
**Target:** `reconstruction/wip-checkpoint-2026-10-30`, not `master`.  
**Evidence:** user-supplied WebM recordings `tests-conformance-aea_conformance_graph.py - video.webm` and `tests-conformance-test_conformance.py - video.webm`.

## Recorded video fidelity

Both Notepad++ scroll recordings show their source files from opening to final editor line, with overlapping scroll coverage. Both explicitly display UTF-8 and Windows CRLF line endings.

| Historical original path | Recorded displayed lines | Normalised LF code lines | Recorded Windows CRLF characters | Candidate LF characters |
| --- | ---: | ---: | ---: | ---: |
| `tests/conformance/aea_conformance_graphs.py` | 191 | 190 | 6,241 | 6,051 |
| `tests/conformance/test_conformance.py` | 183 | 182 | 8,519 | 8,337 |

The recovered drafts exactly reproduce both **editor line counts and CRLF character counts**. Python 3.11 AST parsing passes. Pinned source hashes enforce stability.

- Graph factories: 12 graph variants for MessagesState ReAct, create-agent style structured output, mapped custom state, functional entrypoint, worker subgraph, uncompiled builder, checkpointer, human approval interrupt, async node, content blocks, structured dict and missing AI response. Original mock models and local tools are preserved.
- Conformance tests: 7 original top-level test functions, with 8 parametrised graph shapes, custom-state mapping, missing-map negative case, functional API mapping, approval interrupts, missing AI response and one separate slow CLI subprocess test.
- **This is video-derived candidate fidelity, not original-byte source certification.** Matching counts do not substitute the original source file bytes.

## Runtime replay

`reconstruction_tools/verify_conformance_video_sources.py` checks transcript source checksums, AST syntax and recorded lengths. The new GitHub Actions workflow uses real offline `inspect-ai` + `langgraph` dependencies on Ubuntu/Windows with Python 3.11/3.12. The non-slow pytest cases run separately from the original slow CLI test to avoid tracer reinitialisation.

No AWS credentials, remote LLMs, paid providers, generated historical capture fixtures or original baseline traces are used. The conformance graphs exclusively use deterministic fake chat models.

## Inventory impact

Restores two original paths: expected historical-path presence **62/117 to 64/117** after merge. Newly added audit and CI files are supplementary, not original historical sources.

**Release boundary:** Do not merge into `master`, claim original-byte equality, or call the AEA v2.2.0 reconstruction complete until the remaining source gaps and fidelity checks are resolved.

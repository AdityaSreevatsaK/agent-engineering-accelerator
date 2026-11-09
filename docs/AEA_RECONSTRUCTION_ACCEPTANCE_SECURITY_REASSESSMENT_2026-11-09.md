# AEA v2.2.0 reconstruction — acceptance and security reassessment

**Review date:** 9 November 2026  
**Target:** reconstruction/wip-checkpoint-2026-10-30 (NOT master)  
**Status:** Engineering reconstruction; not approved as an original-byte-accurate v2.2.0 release.

This is a newly authored **current-code assessment**, not a replacement for the source-video reconstructions of historical docs/acceptance.md and docs/review.md. The latter are provisional under reconstruction_drafts/ and retain their historical recorded claims.

## Evidence levels

- **Source-supported:** inspected reconstructed code implements a documented interface/feature. Not source-video authenticity.
- **CI-verified offline:** actual native offline evaluation and relevant tests have passed on Windows/Ubuntu, Python 3.11/3.12. Not real-provider or production validation.
- **Partial/blocked:** important parts of the recorded decision have not been demonstrated or their evidence is absent.
- **Historical-only:** development-process or historical assessment, not a feature acceptance gate.

## D1–D22: current reconstructed source versus recorded acceptance

| Decision | Current assessment | Evidence and limit |
| --- | --- | --- |
| D1 Strands reference workflow | CI-verified offline | Native Strands starter, calculator and framework adapter tests |
| D2 Deterministic calculator | CI-verified offline | Calculator case dataset/rules and baseline regression checks |
| D3 Offline first; optional real models | Partially demonstrated | Offline simulated Strands/LangGraph agents verified; live provider smoke not part of CI |
| D4 Default payload redaction, explicit opt-in | CI-verified offline, scoped | run.py scrub + opt-in flag; synthetic default/capture E2Es for Strands and LangGraph. Custom agents can still disclose content via custom tools/spans |
| D5 Baseline regression with exit status | CI-verified offline | Real CLI check/compare, immutable disposable baselines, planted defects |
| D6 Curated approximately 8–12 examples | Source-supported | Calculator 10, orders 11, expense 12, triage 12, policy RAG 11, helpdesk 10 |
| D7 OpenTelemetry traces | CI-verified offline | configure_tracing and generated traces.jsonl in example CLI runs |
| D8 Local trace JSONL | Source-supported | JsonlSpanExporter writes local JSONL; no collector required by standard offline path |
| D9 Informational latency/cost, future gates | **Partly met** | Metrics and optional pricing exist; there are no CLI --max-latency or --max-cost blocking options |
| D10 Separate evaluation results and spans | Source-supported | Local Inspect log and separate traces.jsonl under a run directory; case-level correlation and ingestion are not a hosted trace service |
| D11 Dataset/config/source/runtime provenance | **Partly verified, not fully met** | See precise field-level finding below |
| D12 Use proven components | Source-supported | Inspect AI, OpenTelemetry, native framework adapters |
| D13 Validate reuse with a different agent | CI-verified offline | Several distinct simulated workflows and two native adapter families; actual second-client-team adoption not shown |
| D14 Developer schedule/tooling | Historical-only | Original project-process decision; not reproducible as a current code acceptance test |
| D15 Inspect AI runner/storage, not DeepEval | Source-supported | run.py uses Inspect Task and eval, local Inspect logs |
| D16 Scrub Inspect content unless capture | CI-verified offline, scoped | run.py scrub and live saved-output privacy probes; may retain safe-looking identifiers and metadata |
| D17 LangGraph instrumentation via OpenInference | Source-supported | Optional OpenInference integration and redaction environment flags; verify per installed dependency version |
| D18 Redact error messages and tracebacks | Source-supported and unit-tested | run.py.scrub and tracing.py._redact_errors; arbitrary custom span attribute content remains a separate trust boundary |
| D19 Repeated runs and minimum case pass rate | Source-supported, tested | --epochs and --min-case-pass-rate; provider variance not measured |
| D20 Normalise CRLF in dataset digest | Source-supported, tested | dataset.py.dataset_sha256 SHA256 on bytes after CRLF-to-LF replacement |
| D21 Concurrency cap in metadata | Source-supported, tested | --max-samples is forwarded into Inspect eval and recorded in run metadata |
| D22 Common trace summary, not trace rewriting | Source-supported | trace_summary.py is consumed when reporting, original trace records remain separate |

The current code remains a reconstructed candidate. Passing an implementation test cannot certify the archived historical sources are byte-identical.

## D11: specific mismatch requiring attention

The historical acceptance draft labels D11 **Met** and describes dataset hash, config hash, source revision when available, and runtime/library versions.

Actual source-level observations from the reconstructed branch:

| Provenance item | Actual implementation | Assessment |
| --- | --- | --- |
| Dataset identity | dataset_path, dataset_sha256, dataset_format_version | Recorded in task metadata |
| Agent/runtime selection | agent, adapter, epochs | Recorded in task metadata |
| State and configuration references | Optional config path, input_map, output_map and judge references | References only; config file contents are not hashed |
| Run identity and execution settings | run_id, capture_content, max_samples | Recorded in run metadata |
| Accelerator version | accelerator_version from installed distribution | Recorded |
| Config file content checksum | No config_sha256/config_hash metadata field | **Not established** |
| Source commit/revision | No git_sha, source_revision or commit_sha metadata field | **Not established** |
| Python and dependency version inventory | No dependency_versions, package_versions or runtime_versions metadata field | **Not established** |

Source anchors: src/agent_accelerator/run.py build_task() metadata, run_task() eval metadata, src/agent_accelerator/config.py load_config() and src/agent_accelerator/dataset.py dataset_sha256().

The presence of a configuration **path** is not a configuration content hash. The presence of an AEA distribution **version** is not proof of the Python, Inspect AI, LangGraph, Strands and other installed versions.

**Decision:** D11 is *partially verified in the reconstructed implementation*. Preserve the historical transcript's wording but do **not** reuse its "Met" verdict as a current assurance claim. A future production hardening change can add these fields separately after historical source-fidelity work or with explicitly documented divergence.

## Security, privacy and retention: updated risk boundaries

The original review was limited in scope and did not cover every later LangGraph path or demo. The additional CI privacy checks improve confidence in reconstructed default log handling, **not** the security of arbitrary real client agents.

1. **Code trust:** CLI agent, custom scorer and custom state-map references are dynamic Python imports. They are executed code, not sandboxed extensions. Custom agents, tools and scorers may read files, issue requests or perform external actions despite logs being scrubbed.
2. **Capture:** With --capture-content, Inspect logs and trace attributes can retain raw prompts, tool outputs and other private information. Never publish captured customer logs or use them as shareable baselines. The baseline update command refuses explicit capture, but this is not comprehensive data-loss prevention.
3. **Default-mode limits:** Sample input/target, messages, model answer text, certain errors and sensitive framework trace attributes are redacted. Identifiers, tool names, case/check labels, paths, model IDs and certain derived statistics can still disclose context. Arbitrary custom tracing attributes may require additional review.
4. **Retention:** Runs, exported reports and intentionally committed baselines require an operator retention policy. There is no built-in age-based cleanup/retention gate. The offline CI privacy probes use temporary files, but production operators must manage long-lived data.
5. **Source integrity:** The historical uv.lock remains missing; tests install allowed dependency ranges, not the original locked installation. Native CI therefore demonstrates reconstructed compatibility, not historical dependency reproducibility.
6. **Original acceptance:** The original CI file remains archived and inactive; original baselines (14), calculator capture fixtures (2) and original acceptance/security documents (2) remain absent. Do not generate fabricated replacements.

## Read-only automated reassessment

Run from the project root with Python 3.11+:

~~~sh
python -m reconstruction_tools.audit_acceptance_source_contract
python -m reconstruction_tools.audit_acceptance_source_contract --format json
python -m unittest reconstruction_tools.test_acceptance_source_contract -v
python -m reconstruction_tools.audit_release_evidence --format markdown
~~~

The new audit reads Python source AST without importing the reconstructed runtime. It checks command names, TOML keys, source-level metadata fields, CRLF digest normalisation and scrub assignments. It flags a change to recorded behaviour and requires D11 re-review if new provenance metadata fields appear. This is **not** an execution security scanner or release sign-off.

## Recommended release work, in order

1. Complete original-video fidelity review and record substantive compatibility corrections.
2. Determine leadership-approved treatment of unavailable historical baseline/capture data, including privacy review.
3. Add production-grade reproducibility provenance (config content hash, Git revision, runtime/library versions) as an **explicit post-reconstruction enhancement** if required by delivery teams.
4. Run a full security review of real integrations, custom scorer/tool side effects, captured content and dependency resolution.
5. Obtain real multi-team adoption evidence and approve final release acceptance before merging to master.

Historical files and 117-file inventory remain untouched by this reassessment.

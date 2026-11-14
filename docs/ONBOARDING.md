# AEA 2.2.0: first evaluation onboarding

**Status:** Self-service, local, synthetic-data onboarding. This guide is not proof that independent delivery engineers have adopted AEA.

## A 15-minute guided path (target, not measured)

The steps use native Windows PowerShell or a Unix shell, Python 3.11/3.12 and the pinned `uv.lock`. No model-provider credentials are required for the included deterministic applications.

1. At the AEA repository root, run:

   ```sh
   python -m pip install uv
   uv lock --check
   uv sync --python 3.11 --all-extras --group dev --locked
   uv run --locked aea --help
   ```

2. Select a standalone synthetic integration:

   ```sh
   cd integrations/equipment_strands
   uv run --locked aea doctor dataset.jsonl --config aea.toml
   ```

   The doctor validates JSONL cases and checks that the selected `module:function` agent and mappers can be **imported**. It does not call agent factories, scorers or models, and AEA does not create evaluation runs. **Importing Python modules still executes top-level code and may create `__pycache__` or run application-defined side effects. Use only trusted code.** Doctor cannot prove a LangGraph state shape, real provider access or runtime correctness. It prints advisory mapper notes where appropriate.

3. Run the first controlled baseline and comparison from the same integration directory:

   ```sh
   uv run --locked aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
   uv run --locked aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1
   uv run --locked aea check dataset.jsonl --config aea.toml --agent agent:build_broken_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
   ```

   The final command deliberately exits **1** for an injected regression. Inspect its comparison report and the retained baseline. The first two commands should exit **0**. Use a dedicated ignored `runs/` directory; do not publish raw outputs without review.

4. For the LangGraph custom-state mapping example, return to the repository root, enter `integrations/vendor_langgraph` and repeat step 2. Its `aea.toml` specifies both `input_map` and `output_map`, because its state does not expose the default messages channel.

## Diagnosing common failures

| Symptom | Meaning and corrective action |
| --- | --- |
| `file not found` or malformed TOML | Supply `--config` relative to your **current working directory**; only `adapter`, `agent`, `input_map` and `output_map` are recognised |
| `cannot import module` | Run from the application directory or install your application package; use a genuine `module:function` reference |
| Missing transitive dependency | Check the error's missing dependency name and the selected optional adapter extra. Doctor does not install packages |
| `graph has no 'messages' channel` | For a LangGraph custom-state graph, provide a callable `--input-map module:function` that returns an input dictionary |
| `NoAnswerError` | Provide an `--output-map module:function` for outputs without an `AIMessage` or `structured_response` |
| AEA exit code 1 | The **check** quality gate detected a regression; read the comparison report |
| AEA exit code 2 | Command or execution error; inspect stderr without enabling content capture |
| Existing baseline update lock | Never automatically remove it. Follow [operational recovery](OPERATIONAL_READINESS.md) |

## Onboarding completion criteria

Record the target environment and actual operator minutes. A successful independent onboarding trial must show: a valid doctor result, one passing baseline, one unchanged comparison, one actionable intentional regression, and no unapproved data capture. Record any undocumented steps or support time.

`aea doctor` is preflight assistance, **not** an agent sandbox, a guarantee that imports are free of side effects or an independent adoption study. To collect real adoption evidence, use [the pilot guide](PILOT.md) and [adoption evidence protocol](ADOPTION_EVIDENCE.md).

# AEA usage

## Agent factories

Provide `module:function` through `--agent`, or in a TOML configuration. The function must construct an independently usable Strands agent or local LangGraph graph for each evaluation.

## Datasets

Use one JSON object per line with a unique `id` and an `input`. Optional expectations include `expected_output`, `output_contains`, `output_not_contains`, `expected_json_schema`, `expected_tool_calls`, `expected_tools`, `forbidden_tools`, `tool_order`, `expected_tool_args` and `expect_interrupt`. Invalid `expected_json_schema` definitions fail during dataset validation, before agent execution.

## Commands

`aea init PATH`: create a starter agent and dataset.

`aea run DATASET --agent module:factory --adapter strands`: evaluate an agent.

`aea check DATASET ... --baseline PATH --update-baseline`: create or update a baseline after validating the target path. An update retains the previous baseline at a sibling `.NAME.aea-backup-*/previous` path and rejects unrelated files. Backups are not deleted automatically. On POSIX, newly frozen snapshot folders and files are restricted to owner-only permissions; Windows ACL configuration still needs review. Do not point this command at unrelated user data or run concurrent writers.

`aea check DATASET ... --baseline PATH`: compare the latest evaluation with the saved baseline.

`aea backups BASELINE`: read-only inventory of previously retained baseline folders. It never deletes, edits or restores data. Inspect each listed backup's contents, access permissions, ownership and retention policy before manually removing anything.

`aea compare BASELINE CURRENT`: compare two existing logs or run directories.

`aea report RUN`: render a Markdown summary.

`aea export report.md --format html`: create a self-contained HTML report. PDF requires a local supported Chromium browser.

For evaluations with multiple epochs, the existing estimated cost describes a normalised single pass through the cases. Reports additionally show summed provider-reported tokens across all epochs and an estimated total evaluation cost when every epoch supplies both token counts. Partial usage produces an explicit `n/a` total instead of silently treating missing usage as zero. These are estimates based on user-supplied USD prices, not billing records.

Use `aea --help` and `aea COMMAND --help` for all flags.

## Local smoke checks

```sh
uv run --locked python scripts/check_examples.py
```

All sample models run locally. Never enable a live-agent factory or a paid judge in automated CI without explicit approval.

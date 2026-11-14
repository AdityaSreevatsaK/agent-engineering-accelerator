# Architecture

AEA is a Python CLI and library that evaluates independently supplied agents.

1. `dataset.py` validates the JSONL case schema.
2. `adapters/strands.py` and `adapters/langgraph.py` convert framework runs to Inspect AI solver outputs.
3. `scorers.py`, `tool_metrics.py` and `judge.py` evaluate answers, tool behaviour and optional model-based judgements.
4. `run.py` creates evaluation logs and strips payload content unless capture was requested.
5. `tracing.py` collects local OpenTelemetry spans and minimises default trace attributes.
6. `compare.py`, `stats.py` and `readings.py` calculate change and significance.
7. `report.py`, `trace_summary.py` and `export.py` create human-readable outputs.

Factories and custom scorers run trusted Python code. The package does not isolate them in a sandbox. Framework/provider configuration belongs to the supplied agent, not AEA.

Default evaluation artefacts provide debugging metrics rather than full anonymisation. Review all outputs before sharing them outside your team.

For an executive architecture diagram, responsibility boundaries and live demonstration narrative, see the [leadership showcase](LEADERSHIP_SHOWCASE.md). For measured versus hypothetical business outcomes, see the [value assessment](VALUE_ASSESSMENT.md).

# Agent Engineering Accelerator (AEA)

**Test existing AI agents, catch regressions and generate readable reports.**

AEA supports **AWS Strands** and **LangGraph**. The examples run locally, with no cloud account, API keys, Docker or WSL.

## Get started

**[Open the simple, step-by-step guide](docs/STEP_BY_STEP.md)**

Start with the **Before you start** section, open Windows PowerShell, and copy the commands for the flow you want.

The guide covers setup, Strands, LangGraph, creating an agent, demonstrations, testing, benchmarks, reports and troubleshooting. All example flows have expected results and output locations.

## What AEA does

| Feature | Purpose |
| --- | --- |
| Agent tests | Check answers, JSON structure and tool use |
| Regression checks | Compare new behaviour against a saved baseline |
| Framework support | Evaluate Strands and LangGraph agents |
| Quality reports | Generate Markdown, HTML and trace summaries |
| Optional advanced checks | LLM judging, quality thresholds and statistics |

## More information

- [Architecture](docs/ARCHITECTURE.md) and [technical usage](docs/USAGE.md)
- [Testing and CI](docs/TESTING.md)
- [Leadership demonstration](docs/DEMO.md) and [value assessment](docs/VALUE_ASSESSMENT.md)
- [Security and operational recovery](docs/OPERATIONAL_READINESS.md)
- [Release decision and remaining approvals](docs/RELEASE_DECISION.md)
- [Independent pilot and measured adoption](docs/PILOT.md)
- [Guide for coding agents and maintainers](AGENTS.md)

## Current status

**v2.2.0 is a tested development candidate on `dev`, not an approved production release.**

The shipped examples are synthetic, not evidence of adoption by other teams. Real agent integration requires the application's code and test cases. Security approval is required before testing confidential data. Default redaction still leaves some identifiers and paths in reports.

`master` is unchanged until explicitly approved for release.

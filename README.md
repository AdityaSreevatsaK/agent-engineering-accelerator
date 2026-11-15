# Agent Engineering Accelerator (AEA)

Evaluation and regression-testing tools for AI agents, built around **Inspect AI** and **OpenTelemetry**.

> **Development status:** The current v2.2.0 candidate lives on the [`dev` branch](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/tree/dev). The default `master` branch is **incomplete** and must not be treated as a working release. AEA has **not** been approved for production use or independently validated with other teams.

## What the development candidate covers

- Test agent outputs, expected tool usage and structured responses against example datasets.
- Evaluate **AWS Strands** and **LangGraph** agents using framework adapters.
- Compare runs against saved baselines to detect regressions.
- Generate reports and trace summaries; optionally run model-based judging.
- Exercise included synthetic examples locally without paid model calls.

These are development capabilities, **not a claim of production readiness**. Real-agent integration, privacy controls and dependency approvals require independent review.

## Get started

**[Step-by-step Windows PowerShell guide](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/blob/dev/docs/STEP_BY_STEP.md)**

The guide covers prerequisites, copy-and-paste commands, Strands and LangGraph example flows, reports and troubleshooting. It intentionally uses `dev`.

```powershell
git clone --branch dev https://github.com/AdityaSreevatsaK/agent-engineering-accelerator.git
Set-Location agent-engineering-accelerator
```

Follow the installation and evaluation commands in the guide rather than using the incomplete default branch.

## Reference

- [Current source code](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/tree/dev)
- [Architecture and usage](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/blob/dev/docs/ARCHITECTURE.md)
- [Testing and CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/blob/dev/docs/TESTING.md)
- [Release decision and outstanding requirements](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/blob/dev/docs/RELEASE_DECISION.md)
- [GitHub Actions](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions)

**Release boundary:** No production release, publication or `dev` to `master` merge is implied by this README update. Independent pilots, security and licence decisions, and explicit release approval remain outstanding.

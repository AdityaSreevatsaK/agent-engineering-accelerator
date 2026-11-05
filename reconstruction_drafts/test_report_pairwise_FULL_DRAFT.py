from pathlib import Path

from agent_accelerator import readings
from agent_accelerator.compare import RunResults
from agent_accelerator.judge import BASELINE_AGENT_ERROR, NOT_IN_BASELINE, JudgedEpoch
from agent_accelerator.report import render_run

MODEL = "judge/m"


def epoch(case_id, outcome, mode="pairwise", **fields) -> JudgedEpoch:
    return JudgedEpoch(case_id, outcome, mode, MODEL, **fields)


def judge_bullets(*epochs: JudgedEpoch) -> dict[str, str]:
    """The Judge section's top-level bullets as {label: value}, in report order."""
    run = RunResults(
        run_id="run", log_path=Path("run.json"), dataset_sha256=None, status="success", cases={}, judge=epochs
    )
    lines = render_run(run).splitlines()
    section = lines[lines.index("## Judge") + 1 :]
    section = section[: next((i for i, line in enumerate(section) if line.startswith("## ")), len(section))]
    return dict(line[2:].split(": ", 1) for line in section if line.startswith("- "))


PAIRWISE_RUN = (
    epoch("a", "pass", pairwise="better"),
    epoch("b", "pass", pairwise="same", order_disagreed=True),
    epoch("c", "fail", pairwise="worse"),
    epoch("d", "pass", pairwise="same"),
    epoch("e", "not_judged", not_judged=NOT_IN_BASELINE),
    epoch("f", "not_judged", not_judged=BASELINE_AGENT_ERROR),
    epoch("g", "not_judged", not_judged="agent_error"),
    epoch("h", "error"),
)


def test_pairwise_judge_section_counts_baseline_gaps_verdicts_and_order_disagreements_apart_from_agent_errors():
    # Expected from the epochs: gaps e and f; better a, same b and d, worse c; one disagreement, b; agent error g.
    # Witnesses: "s33 report agent errors include gaps" counts 3 agent errors; "s33 report gaps include agent
    # errors" counts 3 gaps; "s33 report worse counted as same" and "s33 report disagreements fixed" change their
    # lines; "s33 report pairwise lines dropped" loses all three.
    bullets = judge_bullets(*PAIRWISE_RUN)

    assert bullets["Mode"] == "pairwise"
    assert bullets["Judged"] == "4 of 8 cases"
    assert bullets["Not judged (agent error)"] == "1"
    assert bullets["Not judged (no baseline answer)"] == "2"
    assert bullets["Against the baseline"] == "1 better, 2 same, 1 worse"
    assert bullets["Order disagreements (counted as same)"] == "1"
    assert list(bullets).index("Not judged (no baseline answer)") == list(bullets).index("Not judged (agent error)") + 1


def test_a_non_pairwise_judge_section_has_no_pairwise_lines_and_counts_every_skipped_epoch_as_an_agent_error():
    # A golden run: the labels are those of the section before pairwise existed, and the epoch with no score
    # (not_judged None) still counts with the agent errors.
    # Witness: "s33 report pairwise lines always" (drop the guard) adds the three pairwise lines with zeros.
    bullets = judge_bullets(
        epoch("a", "pass", mode="golden"),
        epoch("b", "fail", mode="golden"),
        epoch("c", "not_judged", mode="golden", not_judged="agent_error"),
        JudgedEpoch("d", "not_judged", None, None),
    )

    assert list(bullets) == [
        "Mode",
        "Judge model",
        "Judged",
        "Judge passed",
        "Judge errors",
        "Not judged (agent error)",
    ]
    assert bullets["Not judged (agent error)"] == "2"


def test_a_pairwise_report_explains_pairwise_in_its_glossary_and_a_golden_one_does_not():
    # Witness: "s33 glossary pairwise always" adds the paragraph to a golden report; "s33 glossary pairwise
    # dropped" loses it from the pairwise one.
    def report(*epochs):
        return render_run(
            RunResults(
                run_id="run", log_path=Path("run.json"), dataset_sha256=None, status="success", cases={}, judge=epochs
            )
        )

    pairwise, golden = report(*PAIRWISE_RUN), report(epoch("a", "pass", mode="golden"))

    glossary = pairwise[pairwise.index("## How to read this report") :]
    assert readings.GLOSSARY["pairwise"] in glossary
    assert readings.GLOSSARY["pairwise"] not in golden
    assert readings.GLOSSARY["judge error"] in golden

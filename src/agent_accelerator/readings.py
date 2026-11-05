"""Plain-English readings for the run and comparison reports, computed from the results.

Everything here is additive: the reports keep their figures, and these lines say what the figures mean for
someone who has not met the statistics behind them. Readings never claim more than the evidence supports.
"""

import math

from agent_accelerator.compare import SIGNIFICANCE_ALPHA, CaseResult, Comparison, MedianChange, RunResults, Statistics
from agent_accelerator.judge import BASELINE_GAPS, INTERRUPTED, JudgedEpoch
from agent_accelerator.run_metrics import check_failures, output_consistency, percentile
from agent_accelerator.stats import wilson_interval
from agent_accelerator.tool_metrics import run_tool_use

SHOWN = 5  # cases named in one sentence before "and N more"
WIDE_INTERVAL = 0.5  # a 95% range wider than half the scale is called rough
FEW_PAIRED_CASES = 20  # below this many shared cases, the comparison says its evidence is weak
LONG_TAIL = 2.0  # p95 latency at least this many times p50 is called a long tail
FEW_EPOCHS = 5  # below this, a significant Fisher fall gets a "rerun to confirm" reading
MIN_KAPPA_LABELS = 10  # below this many human-labelled cases, kappa is too unstable to print
# Landis and Koch (1977) bands for kappa: (upper bound, agreement beyond chance below it)
KAPPA_BANDS = ((0.0, "no"), (0.2, "slight"), (0.4, "fair"), (0.6, "moderate"), (0.8, "substantial"))
TRUSTED_KAPPA = 0.6  # below this, the kappa reading says to spot-check the judge

GLOSSARY = {
    "wilson": "**Wilson interval** (the bracketed range after a pass rate): the range the true pass rate probably "
    "lies in (95% confidence), given how few tries there were; it narrows as you add epochs.",
    "pass@k": "**pass@k**: the chance that at least one of k tries passes; useful when a failed try can simply be "
    "retried.",
    "pass^k": "**pass^k**: the chance that all k tries pass; the one to watch when a user gets a single attempt.",
    "percentile": "**Percentiles (p50, p90, p95)**: the value that 50%, 90% or 95% of tries were at or below, so p50 "
    "is the typical try and p95 the slow end.",
    "newcombe": "**Newcombe interval**: the range the true change in pass rate probably lies in (95% confidence); "
    "if it includes 0, the change could be noise.",
    "mcnemar": "**McNemar test**: looks only at the cases that flipped between pass and fail, and asks whether flips "
    "in one direction outnumber the other by more than chance would explain.",
    "fisher": "**Fisher exact test**: for one case run several times on each side, asks how likely a fall in passes "
    "at least this large would be if the agent had not changed.",
    "bootstrap": "**Bootstrap interval**: resamples the per-case changes many times to find the range the typical "
    "change probably lies in; if it includes 0, there is no consistent change.",
    "p-value": "**p-value**: the chance of a difference at least this large if nothing had really changed; 0.05 or "
    "less suggests a real change, larger values mean it could well be chance.",
    "judge error": "**Judge error**: a try the judge could not score, because its reply was not in the expected "
    "shape or the model call failed. It is reported as an error, not as a judge verdict, and the try does not pass.",
    "reference-free": "**Reference-free**: the judge grades an answer against the rubric criteria alone, because "
    "the case has no reference answer in the golden file; golden mode compares the answer with that reference.",
    "pairwise": "**Pairwise**: the judge compares each answer with the baseline run's answer to the same case and "
    "says whether it is better, the same or worse. It is asked twice, with the two answers in each order; if the "
    "verdict changes with the order, the order decided it rather than the content, so it counts as the same. A worse "
    "answer fails the try; better and the same pass it.",
    "kappa": "**Cohen's kappa**: how far the judge and the human labels agree beyond what chance alone would give; "
    "1 is perfect agreement, 0 is no better than chance, below 0 is worse than chance. It needs enough labelled "
    "cases to be stable.",
}

NOTES = {
    "reliability": "pass@1 is the average share of tries that passed. pass@k is the chance that at least one of k "
    "tries passes; pass^k is the chance that all k pass, the one to watch when users get one attempt. The bracketed "
    "range is where each case's true pass rate probably lies, given this few runs.",
    "tool_use": "Every tool call the agent made. Errors are calls whose result was an error; redundant calls repeat "
    "an earlier identical call and usually waste time and tokens. Precision is the share of tools called that were "
    "expected; recall is the share of expected tools that were called.",
    "performance": "How long tries took and how many tokens they used, over every case-epoch. p50 is the typical "
    "try; p90 and p95 are the slow end (90% or 95% of tries were at or below it); max is the worst single try.",
    "failures": "Each failing check, counted once per try (case-epoch) it failed in. Failing epochs is how often it "
    "failed; Cases is how many different cases it hit.",
    "consistency": "How often each case gave the same final answer across its epochs: 100% means the same answer "
    "every time, lower means the answer changed between tries.",
    "judge": "The LLM judge's verdicts on the agent's answers. Golden mode compares an answer with a reference "
    "answer; reference-free mode grades it against rubric criteria alone. Judge errors are tries the judge could "
    "not score; agent errors are not judged at all. Calibration compares the judge with human labels, where the "
    "golden file has them.",
    "statistics": "Whether the differences between the two runs are bigger than chance would explain. Ranges are "
    "95%; changes are current minus baseline.",
}


def note(key: str) -> str:
    return f"_{NOTES[key]}_"


def reading_lines(readings: list[str]) -> list[str]:
    """Readings as indented sub-bullets after a blank line; nothing when there is nothing to say."""
    return ["", *(f"  - {r}" for r in readings)] if readings else []


def glossary_lines(keys: list[str], after: list[str]) -> list[str]:
    """The closing glossary, one paragraph per method used; nothing when the report uses none.

    after is the report so far, so the heading gets exactly one blank line above it.
    """
    if not keys:
        return []
    lines = ([] if after and after[-1] == "" else [""]) + ["## How to read this report"]
    for key in dict.fromkeys(keys):
        lines += ["", GLOSSARY[key]]
    return lines


def counted(n: int, singular: str, plural: str) -> str:
    """n with its noun in the right number: "1 epoch", "2 epochs", "0 epochs"."""
    return f"{n} {singular if n == 1 else plural}"


def _names(ids: list[str]) -> str:
    """Up to SHOWN names as an English list: "a", "a and b", "a, b and c", "a, b, c, d, e and 2 more"."""
    shown = ids[:SHOWN] + ([f"{len(ids) - SHOWN} more"] if len(ids) > SHOWN else [])
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def _by_id(run: RunResults) -> list[CaseResult]:
    return sorted(run.cases.values(), key=lambda c: c.id)


def _never_passed(cases: list[CaseResult]) -> list[CaseResult]:
    return [c for c in cases if c.passes == 0]


# Run report


def _epoch_text(cases: list[CaseResult]) -> str:
    fewest, most = min(c.runs for c in cases), max(c.runs for c in cases)
    if most == 1:
        return ""
    return f", each run {most} times" if fewest == most else f", each run {fewest} to {most} times"


def _overall_sentence(run: RunResults, cases: list[CaseResult]) -> str:
    passed = sum(c.passed for c in cases)
    errored = sum(c.error is not None for c in cases)
    text = f"{passed} of {len(cases)} cases passed ({passed / len(cases):.0%}){_epoch_text(cases)}"
    text += f", and {errored} ended with an error." if errored else "."
    if run.status != "success":
        text = f"The run ended with status {run.status!r}, so results may be incomplete. {text}"
    return text


def _unreliable_sentence(cases: list[CaseResult]) -> str | None:
    flaky = [f"{c.id} ({c.passes}/{c.runs})" for c in cases if c.flaky]
    never_cases = _never_passed(cases)
    never = [c.id for c in never_cases]
    if all(c.runs == 1 for c in never_cases):
        label = "Failed"
    elif all(c.runs > 1 for c in never_cases):
        label = "Failed every epoch"
    else:
        label = "Never passed"
    parts = []
    if flaky:
        parts.append(f"flaky (passed some epochs but not all): {_names(flaky)}")
    if never:
        parts.append(f"{label.lower()}: {_names(never)}")
    if not parts:
        return None
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + "."


def _top_checks(run: RunResults) -> tuple[list[str], int, int] | None:
    """(tied most common checks, their failing epochs, cases hit by the first) or None when nothing failed."""
    checks = check_failures(run)
    if not checks:
        return None
    top = checks[0][1]
    return [name for name, count, _ in checks if count == top], top, checks[0][2]


def _check_sentence(run: RunResults) -> str | None:
    top = _top_checks(run)
    if top is None:
        return None
    names, count, cases = top
    tries = sum(len(c.epochs) for c in run.cases.values())
    if len(names) > 1:
        return f"The most common failing checks are {_names(names)}, each failing in {count} of {tries} tries."
    return f"The most common failing check is {names[0]}, failing in {count} of {tries} tries across {cases} case(s)."


def _tool_error_sentence(cases: list[CaseResult]) -> str | None:
    use = run_tool_use(c.tool_use for c in cases)
    if use is None or not use.errors:
        return None
    erring = [c for c in cases if c.tool_use is not None and c.tool_use.errors]
    named = [f"{c.id} ({c.tool_use.errors})" for c in erring if c.tool_use is not None]
    text = f"{use.errors} tool call(s) returned an error, in {_names(named)}"
    if all(c.passes == c.runs for c in erring):
        those = "that case" if len(erring) == 1 else "those cases"
        return text + f"; {those} still passed every time, so the errors may be expected."
    return text + "."


def _slowest_sentence(cases: list[CaseResult]) -> str | None:
    timed = [c for c in cases if c.latency_s is not None]
    if len(timed) < 2:
        return None
    slowest = max(timed, key=lambda c: c.latency_s or 0.0)  # max keeps the first, so ties go to the lowest id
    median_note = " (median across its epochs)" if slowest.runs > 1 else ""
    return f"The slowest case is {slowest.id} at {slowest.latency_s:.3f}s{median_note}."


def summary_lines(run: RunResults) -> list[str]:
    """The run report's Summary: a few sentences computed from the results, each omitted when it has nothing to say."""
    cases = _by_id(run)
    if not cases:
        return ["## Summary", "", "No cases ran.", ""]
    sentences = [
        _overall_sentence(run, cases),
        _unreliable_sentence(cases),
        _check_sentence(run),
        _tool_error_sentence(cases),
        _slowest_sentence(cases),
    ]
    return ["## Summary", "", " ".join(s for s in sentences if s), ""]


def reliability_readings(cases: list[CaseResult], k: int, at_k: float, hat_k: float) -> list[str]:
    readings = []
    flaky = [c for c in cases if c.flaky]
    for case in flaky[:SHOWN]:
        low, high = wilson_interval(case.passes, case.runs)
        readings.append(
            f"{case.id} passed {case.passes} of {case.runs}; its true pass rate could be anywhere from {low:.0%} "
            f"to {high:.0%}, so run more epochs to narrow it."
        )
    if len(flaky) > SHOWN:
        readings.append(f"{len(flaky) - SHOWN} more flaky case(s) read the same way; see the table.")
    never = [c for c in _never_passed(cases) if c.runs > 1]
    if never:
        ceiling = max(wilson_interval(0, c.runs)[1] for c in never)
        readings.append(
            f"{_names([c.id for c in never])} failed every epoch; the true pass rate is probably no higher than "
            f"{ceiling:.0%}."
        )
    solid = [c for c in cases if c.passes == c.runs]
    if solid:
        floor = min(wilson_interval(c.passes, c.runs)[0] for c in solid)
        readings.append(
            f"{len(solid)} case(s) passed every epoch; even so, with this few tries their true pass rate could be "
            f"as low as {floor:.0%}."
        )
    points = math.floor((at_k - hat_k) * 100 + 0.5)  # half up, so a gap shown is at least 1 point
    if points >= 1:
        unit = "point" if points == 1 else "points"
        readings.append(
            f"pass@{k} is {points} {unit} above pass^{k}: retrying hides failures that a user with one "
            "attempt would see."
        )
    if any(high - low > WIDE_INTERVAL for low, high in (wilson_interval(c.passes, c.runs) for c in cases)):
        readings.append(
            f"Some ranges span more than half the scale; at {counted(k, 'epoch', 'epochs')} per case, treat per-case "
            "rates as rough."
        )
    return readings


def tool_use_readings(cases: list[CaseResult]) -> list[str]:
    use = run_tool_use(c.tool_use for c in cases)
    if use is None:
        return []
    readings = []
    if use.errors:
        named = [f"{c.id} ({c.tool_use.errors})" for c in cases if c.tool_use is not None and c.tool_use.errors]
        readings.append(f"{use.errors} call(s) returned an error, in {_names(named)}; check whether that was expected.")
    if use.redundant:
        named = [f"{c.id} ({c.tool_use.redundant})" for c in cases if c.tool_use is not None and c.tool_use.redundant]
        readings.append(f"{use.redundant} call(s) repeated an identical earlier call, in {_names(named)}.")
    if use.results and not use.errors and not use.redundant:
        readings.append("No tool errors and no repeated calls.")
    if use.precision is not None and use.precision < 1:
        readings.append("Precision below 100% means the agent called tools some cases did not expect.")
    if use.recall is not None and use.recall < 1:
        readings.append("Recall below 100% means the agent skipped tools some cases expected.")
    return readings


def performance_readings(run: RunResults) -> list[str]:
    latencies = [e.latency_s for c in run.cases.values() for e in c.epochs if e.latency_s is not None]
    if not latencies:
        return []
    p50, p95 = percentile(latencies, 50), percentile(latencies, 95)
    if p95 == 0 or (p50 > 0 and p95 < LONG_TAIL * p50):  # a p50 of 0 under a positive p95 is not steady
        return [f"Latency is steady: even the slow end (p95) is within {LONG_TAIL:g} times the typical try."]
    slow = sum(latency >= p95 for latency in latencies)
    if p50 > 0:
        compared = f"{p95 / p50:.1f} times the typical try"
    else:
        compared = "while the typical try took no measurable time"
    return [f"The slow tail is long: {slow} of {len(latencies)} tries took {p95:.3f}s or more, {compared}."]


def failure_readings(run: RunResults) -> list[str]:
    top = _top_checks(run)
    if top is None:
        return []
    names, count, cases = top
    if len(names) > 1:
        readings = [f"{_names(names)} failed most often ({counted(count, 'try', 'tries')} each); start there."]
    else:
        readings = [f"{names[0]} failed most often ({counted(count, 'try', 'tries')}, {cases} case(s)); start there."]
    failing = [c for c in run.cases.values() if any(e.failed_checks for e in c.epochs)]
    if failing and all(c.flaky for c in failing):
        readings.append(
            "Every failure comes from a case that passes on other tries: the agent is inconsistent rather than "
            "always wrong."
        )
    elif failing and all(c.passes == 0 for c in failing):
        readings.append("Every failure comes from a case that never passed: these are consistent failures.")
    return readings


def consistency_readings(run: RunResults) -> list[str]:
    shares = output_consistency(run)
    if not shares:
        return []
    varied = sorted(case_id for case_id, share in shares.items() if share < 1)
    flaky = sorted(case_id for case_id in shares if run.cases[case_id].flaky)
    if varied:
        readings = [f"{len(varied)} of {len(shares)} case(s) gave a different answer in at least one epoch."]
        both = [case_id for case_id in varied if case_id in flaky]
        if both:
            readings.append(
                f"For {_names(both)}, the answer changed along with the result, which likely explains the flaky "
                "passes."
            )
        return readings
    if flaky:
        return [
            "Answers never varied, so the flaky results come from something other than the final answer, such "
            "as the tool calls."
        ]
    return []


def run_glossary_keys(has_reliability: bool, has_performance: bool) -> list[str]:
    keys = ["wilson", "pass@k", "pass^k"] if has_reliability else []
    return keys + (["percentile"] if has_performance else [])


def _judge_counts(epochs: tuple[JudgedEpoch, ...], outcome: str) -> list[str]:
    """Cases with this outcome, each with its count when the run had several epochs, by case id."""
    counts: dict[str, int] = {}
    for epoch in epochs:
        if epoch.outcome == outcome:
            counts[epoch.case_id] = counts.get(epoch.case_id, 0) + 1
    several = len(epochs) > len({e.case_id for e in epochs})
    return [f"{case_id} ({n})" if several else case_id for case_id, n in sorted(counts.items())]


def _kappa_band(kappa: float) -> str:
    return next((band for upper, band in KAPPA_BANDS if kappa <= upper), "almost perfect")


def judge_readings(
    epochs: tuple[JudgedEpoch, ...], pairs: list[tuple[str, str, str]], comparable: int, kappa: float | None
) -> list[str]:
    """pairs are (case id, judge verdict, human label) per judged epoch of a labelled golden case; comparable is how
    many labelled cases have a verdict among them."""
    readings = []
    errored = _judge_counts(epochs, "error")
    if errored:
        count = sum(e.outcome == "error" for e in epochs)
        readings.append(
            f"{count} judge error(s), in {_names(errored)}: the judge could not score those tries, so they count as "
            "errors rather than verdicts; check the judge model's replies."
        )
    skipped = sum(e.outcome == "not_judged" and e.not_judged not in (*BASELINE_GAPS, INTERRUPTED) for e in epochs)
    if skipped:
        were, them = ("was", "it") if skipped == 1 else ("were", "them")
        readings.append(
            f"{counted(skipped, 'try', 'tries')} {were} not judged because the agent errored; the judge pass rate "
            f"leaves {them} out."
        )
    interrupted = sum(e.outcome == "not_judged" and e.not_judged == INTERRUPTED for e in epochs)
    if interrupted:
        were, them = ("was", "it") if interrupted == 1 else ("were", "them")
        readings.append(
            f"{counted(interrupted, 'try', 'tries')} {were} not judged because the run stopped at an interrupt, so "
            f"there was no answer; expect_interrupt decides those cases and the judge pass rate leaves {them} out."
        )
    readings += _pairwise_readings(epochs)
    if not any(e.outcome in ("pass", "fail") for e in epochs):
        readings.append("The judge gave no verdicts, so this section says nothing about answer quality.")
    failing: dict[str, list[str]] = {}
    for epoch in epochs:
        if epoch.mode == "reference_free" and epoch.outcome in ("pass", "fail"):
            for name, passed in epoch.criteria:
                failing.setdefault(name, [])
                if not passed:
                    failing[name].append(epoch.case_id)
    top = max((len(ids) for ids in failing.values()), default=0)
    if top:
        names = [name for name, ids in failing.items() if len(ids) == top]
        if len(names) > 1:
            readings.append(f"{_names(names)} failed most often ({counted(top, 'try', 'tries')} each); start there.")
        else:
            cases = len(set(failing[names[0]]))
            readings.append(
                f"{names[0]} failed most often ({counted(top, 'try', 'tries')}, {cases} case(s)); start there."
            )
    if pairs:
        disagreed = sorted({case_id for case_id, verdict, label in pairs if verdict != label})
        if disagreed:
            readings.append(
                f"The judge disagreed with the human label on {_names(disagreed)}; read those answers to see which "
                "side is right."
            )
            readings.append(
                "Human labels describe the agent version they were written for, so after an agent change a "
                "disagreement may be the regression rather than a judge fault."
            )
        else:
            readings.append("The judge matched the human label on every labelled case it judged.")
        if comparable < MIN_KAPPA_LABELS:
            readings.append(
                f"Kappa needs at least {MIN_KAPPA_LABELS} labelled cases and there are {comparable}; label more golden "
                "entries before relying on the agreement figure."
            )
        elif kappa is None:
            readings.append(
                "Kappa is undefined: the judge and the humans gave every labelled case the same verdict, so there is "
                "no variation to measure agreement beyond chance."
            )
        else:
            text = f"Kappa {kappa:.2f} means {_kappa_band(kappa)} agreement beyond chance (Landis and Koch bands)"
            readings.append(
                text + ("; spot-check the judge's verdicts before relying on them." if kappa < TRUSTED_KAPPA else ".")
            )
    return readings


def _pairwise_readings(epochs: tuple[JudgedEpoch, ...]) -> list[str]:
    """What the pairwise verdicts say; nothing when no case was judged pairwise."""
    if not any(e.mode == "pairwise" for e in epochs):
        return []
    readings = []
    gaps = [e for e in epochs if e.outcome == "not_judged" and e.not_judged in BASELINE_GAPS]
    if gaps:
        were, them = ("was", "it") if len(gaps) == 1 else ("were", "them")
        readings.append(
            f"{counted(len(gaps), 'try', 'tries')} {were} not judged because the baseline has no answer for "
            f"{_names(sorted((e.case_id for e in gaps)))} (the case is missing from the baseline run, or its agent "
            f"errored or stopped at an interrupt there); the judge pass rate leaves {them} out."
        )
    worse = sorted({e.case_id for e in epochs if e.pairwise == "worse"})
    judged = [e for e in epochs if e.pairwise is not None]
    if worse:
        readings.append(
            f"The answers to {_names(worse)} were worse than the baseline's, so those tries fail the judge; read them "
            "beside the baseline's answers first."
        )
    elif judged:
        better = sum(e.pairwise == "better" for e in judged)
        tail = f"; {counted(better, 'try was', 'tries were')} better" if better else ""
        readings.append(f"No answer was judged worse than the baseline's{tail}.")
    disagreed = [e for e in judged if e.order_disagreed]
    unit = ("try", "tries") if len(epochs) > len({e.case_id for e in epochs}) else ("case", "cases")
    if disagreed:
        readings.append(
            f"The verdict changed when the two answers were swapped on {len(disagreed)} of "
            f"{counted(len(judged), *unit)} ({_names(sorted({e.case_id for e in disagreed}))}), so the order "
            "decided those rather than the content and they count as the same; if that is many, the judge cannot "
            "reliably tell these answers apart."
        )
    return readings


def judge_glossary_keys(epochs: tuple[JudgedEpoch, ...], has_calibration: bool) -> list[str]:
    if not epochs:
        return []
    keys = ["judge error"] + (["reference-free"] if any(e.mode == "reference_free" for e in epochs) else [])
    keys += ["pairwise"] if any(e.mode == "pairwise" for e in epochs) else []
    return keys + (["kappa"] if has_calibration else [])


# Comparison report


def comparison_epochs(cmp: Comparison) -> int:
    """Epochs per case on the side with fewer: one when either run tried each case once."""
    return min(max((c.runs for c in run.cases.values()), default=1) for run in (cmp.baseline, cmp.current))


def evidence_line(stats: Statistics, epochs: int) -> list[str]:
    reasons = []
    if stats.paired < FEW_PAIRED_CASES:
        reasons.append(f"only {stats.paired} case(s) are in both runs")
    if epochs <= 1:
        reasons.append("each case ran once")
    if not reasons:
        return []
    return [f"_Evidence is weak here: {' and '.join(reasons)}, so only large changes can stand out from noise._", ""]


def wilson_verdict(stats: Statistics) -> str:
    base, cur = stats.baseline, stats.current
    text = f"Baseline passed {base.passes} of {base.cases} cases, current {cur.passes} of {cur.cases}. "
    if cur.high < base.low or cur.low > base.high:
        return text + "The two ranges do not overlap, so the pass rate very likely changed."
    tail = "; the change line tests it directly." if stats.difference is not None else "."
    return text + "The ranges overlap, so on their own they do not show a change" + tail


def newcombe_verdict(delta: float, low: float, high: float) -> str:
    bounds = f"{low * 100:+.1f} and {high * 100:+.1f} points"
    if abs(delta) < 0.0005:
        return f"Pass rate did not change, but with this few cases a real change anywhere between {bounds} could hide."
    text = f"Pass rate changed by {delta * 100:+.1f} points; the real change is likely between {bounds}"
    if high < 0:
        return text + ", so this is likely a real drop."
    if low > 0:
        return text + ", so this is likely a real improvement."
    return text + ", which includes 0, so this could be noise."


def _chance(p: float) -> str:
    return "less than 1%" if p < 0.01 else f"about {p:.0%}"


def mcnemar_verdict(stats: Statistics) -> str:
    worse, better, p = stats.passed_to_failed, stats.failed_to_passed, stats.mcnemar_p
    if worse + better == 0:
        return "No case flipped between pass and fail, so there is nothing for this test to weigh."
    flips = f"{worse} case(s) went pass->fail and {better} fail->pass"
    if worse == better:
        return f"{flips}; an even split is what chance alone would give, so this is not conclusive."
    verdict = "so this is not conclusive" if p > SIGNIFICANCE_ALPHA else "so chance alone is an unlikely explanation"
    return f"{flips}; a split this uneven would happen by chance {_chance(p)} of the time, {verdict}."


def bootstrap_verdict(change: MedianChange, up: tuple[str, str], down: tuple[str, str]) -> str:
    """up / down are (direction, what the typical case did), e.g. ("slower", "took 0.078s longer")."""
    if change.low > 0:
        return f"Consistently {up[0]}: the typical case {up[1]}, and the range excludes 0."
    if change.high < 0:
        return f"Consistently {down[0]}: the typical case {down[1]}, and the range excludes 0."
    return "No consistent change: the range includes 0, so this could be noise."


def warning_reading(text: str, epochs: int) -> str | None:
    """A plain reading for the comparison warnings and regressions that need one; None for the rest."""
    if "one-sided Fisher" in text:
        reading = (
            "Each p in brackets is the chance of a fall at least this large if the agent had not changed; at or below "
            "the threshold, the fall is probably real rather than bad luck."
        )
        if epochs < FEW_EPOCHS:
            reading += f" With only {counted(epochs, 'epoch', 'epochs')} per case, rerun with more to confirm."
        return reading
    if "--max-p-value not applied" in text:
        return (
            "With one try per case, a single pass or fail cannot be told apart from chance; rerun both sides with "
            "--epochs 5 or more to use this check."
        )
    if "passed in some epochs but not all" in text:
        return "These cases are unreliable, so one pass or fail for them says little about whether a change helped."
    return None


def comparison_glossary_keys(cmp: Comparison) -> list[str]:
    stats = cmp.statistics
    keys = []
    if stats is not None:
        keys += ["wilson"] + (["newcombe"] if stats.difference is not None else []) + ["mcnemar"]
        keys += ["bootstrap"] if stats.latency_s is not None or stats.tokens is not None else []
    if any("one-sided Fisher" in text for text in [*cmp.regressions, *cmp.warnings]):
        keys.append("fisher")
    return keys + (["p-value"] if keys else [])

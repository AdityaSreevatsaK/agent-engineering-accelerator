"""Compare a run against a baseline, case by case, and decide whether it regressed."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from inspect_ai.log import EvalSample, read_eval_log
from inspect_ai.scorer import CORRECT

from agent_accelerator.judge import JUDGE, JudgedEpoch, judge_error, judged_epochs
from agent_accelerator.run_metrics import EpochMetrics, epoch_metrics
from agent_accelerator.scorers import CASE_CHECKS
from agent_accelerator.stats import (
    bootstrap_median_interval,
    fisher_worse_p,
    mcnemar_exact_p,
    newcombe_difference_interval,
    wilson_interval,
)
from agent_accelerator.tool_metrics import CaseToolUse, case_tool_use

SIGNIFICANCE_ALPHA = 0.05  # warn when a fall in pass rate is this unlikely by chance; p == alpha counts


@dataclass(frozen=True)
class CaseResult:
    id: str
    passed: bool
    error: str | None
    latency_s: float | None
    failures: dict[str, str]  # scorer name -> explanation, for failing scorers only
    runs: int = 1  # epochs this case ran
    passes: int = 0  # epochs in which every scorer passed
    input_tokens: int | None = None  # per-epoch average over epochs that reported usage
    output_tokens: int | None = None
    tool_calls: float | None = None  # per-epoch average; None for logs or adapters that recorded no count
    epochs: tuple[EpochMetrics, ...] = ()  # per-epoch values behind the run report's distributions
    tool_use: CaseToolUse | None = None  # names, errors, redundancy and selection; None for older logs

    @property
    def flaky(self) -> bool:
        return 0 < self.passes < self.runs


@dataclass(frozen=True)
class RunResults:
    run_id: str
    log_path: Path
    dataset_sha256: str | None
    status: str
    cases: dict[str, CaseResult]
    capture_content: bool = False  # run kept unredacted prompts and outputs; False for logs that predate the key
    judge: tuple[JudgedEpoch, ...] = ()  # every case-epoch when the run was judged; empty when no judge ran

    @property
    def pass_rate(self) -> float:
        return sum(c.passed for c in self.cases.values()) / len(self.cases) if self.cases else 0.0

    @property
    def error_rate(self) -> float:
        return sum(c.error is not None for c in self.cases.values()) / len(self.cases) if self.cases else 0.0

    @property
    def median_latency_s(self) -> float | None:
        values = [c.latency_s for c in self.cases.values() if c.latency_s is not None]
        return median(values) if values else None

    @property
    def input_tokens(self) -> int | None:
        return _total(c.input_tokens for c in self.cases.values())

    @property
    def output_tokens(self) -> int | None:
        return _total(c.output_tokens for c in self.cases.values())


def _total(values: Iterable[int | None]) -> int | None:
    """Sum of the reported values; None when nothing reported."""
    reported = [v for v in values if v is not None]
    return sum(reported) if reported else None


@dataclass(frozen=True)
class Thresholds:
    max_new_failures: int = 0
    max_pass_rate_drop: float = 0.0  # fraction, e.g. 0.05 allows a five-point drop
    max_error_rate_increase: float = 0.0
    max_p_value: float | None = None  # opt-in: a case or pooled one-sided Fisher p at or below this regresses

    def __post_init__(self) -> None:
        if type(self.max_new_failures) is not int or self.max_new_failures < 0:
            raise ValueError("max_new_failures must be a non-negative integer")
        for name in ("max_pass_rate_drop", "max_error_rate_increase"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a finite fraction between 0 and 1")
        alpha = self.max_p_value
        if alpha is not None and (
            isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 < alpha < 1
        ):
            raise ValueError("max_p_value must be strictly between 0 and 1")


@dataclass(frozen=True)
class RateInterval:
    passes: int
    cases: int
    low: float  # 95% Wilson interval
    high: float

    @property
    def rate(self) -> float:
        return self.passes / self.cases if self.cases else 0.0


@dataclass(frozen=True)
class MedianChange:
    """Median of paired per-case differences (current minus baseline) with a 95% percentile bootstrap interval."""

    median: float
    low: float
    high: float
    pairs: int


@dataclass(frozen=True)
class Statistics:
    """Informational comparison statistics; none of them gates."""

    baseline: RateInterval
    current: RateInterval
    difference: tuple[float, float] | None  # 95% Newcombe interval for current minus baseline pass rate
    paired: int  # cases in both runs
    passed_to_failed: int  # McNemar b
    failed_to_passed: int  # McNemar c
    mcnemar_p: float  # two-sided exact
    latency_s: MedianChange | None = None
    tokens: MedianChange | None = None  # total (input + output) tokens per case


@dataclass
class Comparison:
    baseline: RunResults
    current: RunResults
    newly_failing: list[str] = field(default_factory=list)
    newly_passing: list[str] = field(default_factory=list)
    still_failing: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statistics: Statistics | None = None

    @property
    def regressed(self) -> bool:
        return bool(self.regressions)


def resolve_log(path: Path) -> Path:
    """Accepts a log file or a run directory containing exactly one log."""
    if path.is_file():
        return path
    logs = sorted(path.glob("*.json"))
    if len(logs) != 1:
        raise FileNotFoundError(f"expected one .json eval log in {path}, found {len(logs)}")
    return logs[0]


def load_results(path: Path, min_case_pass_rate: float = 1.0) -> RunResults:
    """A case that ran over several epochs passes when its share of passing epochs reaches min_case_pass_rate."""
    if not 0 <= min_case_pass_rate <= 1:
        raise ValueError("min_case_pass_rate must be a finite fraction between 0 and 1")
    log_path = resolve_log(path)
    log = read_eval_log(log_path)
    epochs: dict[str, list[EvalSample]] = {}
    for sample in log.samples or []:
        epochs.setdefault(str(sample.id), []).append(sample)
    cases = {case_id: _case_result(case_id, samples, min_case_pass_rate) for case_id, samples in epochs.items()}
    metadata = log.eval.metadata or {}  # Inspect merges task and eval metadata here
    return RunResults(
        run_id=str(metadata.get("run_id", log.eval.run_id)),
        log_path=log_path,
        dataset_sha256=metadata.get("dataset_sha256"),
        status=log.status,
        cases=cases,
        capture_content=metadata.get("capture_content") is True,
        judge=judged_epochs(log.samples or []),
    )


def _sample_failures(sample: EvalSample, error: str | None) -> dict[str, str]:
    scores = sample.scores or {}
    failures = {name: s.explanation or f"{name} failed" for name, s in scores.items() if s.value != CORRECT}
    if not scores:
        failures["unscored"] = error or "no scores recorded"
    return failures


def _mean_tokens(samples: list[EvalSample], key: str) -> int | None:
    """Per-epoch average if one or more epochs reported it."""
    usages = [s.metadata.get("usage") for s in samples]
    values = [u[key] for u in usages if isinstance(u, dict) and u.get(key) is not None]
    return round(sum(values) / len(values)) if values else None


def _mean_tool_calls(samples: list[EvalSample]) -> float | None:
    """Per-epoch average of case_checks' tool-call count over epochs that reported it."""
    scores = [(s.scores or {}).get(CASE_CHECKS) for s in samples]
    counts = [c for sc in scores if sc and isinstance(c := (sc.metadata or {}).get("tool_call_count"), int)]
    return sum(counts) / len(counts) if counts else None


def _epoch_error(sample: EvalSample) -> str | None:
    """The agent's error is better than a sample's error; the judge is not an agent error, so ignore it."""
    agent = sample.metadata.get("agent_error") or (sample.error.message if sample.error else None)
    return agent or judge_error((sample.scores or {}).get(JUDGE))


def _case_result(case_id: str, samples: list[EvalSample], min_case_pass_rate: float) -> CaseResult:
    errors = [_epoch_error(s) for s in samples]
    per_epoch = [_sample_failures(s, e) for s, e in zip(samples, errors, strict=True)]
    passes = sum(not f for f in per_epoch)
    latencies = [s.total_time for s in samples if s.total_time is not None]
    return CaseResult(
        id=case_id,
        passed=passes / len(samples) >= min_case_pass_rate - 1e-9,
        error=next((e for e in errors if e), None),
        latency_s=median(latencies) if latencies else None,
        failures=next((f for f in per_epoch if f), {}),  # the first failing epoch's reasons
        runs=len(samples),
        passes=passes,
        input_tokens=_mean_tokens(samples, "inputTokens"),
        output_tokens=_mean_tokens(samples, "outputTokens"),
        tool_calls=_mean_tool_calls(samples),
        epochs=tuple(epoch_metrics(s, f) for s, f in zip(samples, per_epoch, strict=True)),
        tool_use=case_tool_use([(s.scores or {}).get(CASE_CHECKS) for s in samples]),
    )


def compare(baseline: RunResults, current: RunResults, thresholds: Thresholds) -> Comparison:
    result = Comparison(baseline=baseline, current=current)
    for case_id, case in current.cases.items():
        before = baseline.cases.get(case_id)
        if before is None:
            result.added.append(case_id)
        elif before.passed and not case.passed:
            result.newly_failing.append(case_id)
        elif not before.passed and case.passed:
            result.newly_passing.append(case_id)
        elif not case.passed:
            result.still_failing.append(case_id)
    result.removed = sorted(set(baseline.cases) - set(current.cases))

    if current.status != "success":
        result.regressions.append(f"current run status is {current.status!r}")
    if len(result.newly_failing) > thresholds.max_new_failures:
        result.regressions.append(
            f"{len(result.newly_failing)} case(s) newly failing (allowed {thresholds.max_new_failures})"
        )
    drop = baseline.pass_rate - current.pass_rate
    if drop > thresholds.max_pass_rate_drop + 1e-9:
        result.regressions.append(f"pass rate fell {drop:.1%} (allowed {thresholds.max_pass_rate_drop:.1%})")
    rise = current.error_rate - baseline.error_rate
    if rise > thresholds.max_error_rate_increase + 1e-9:
        result.regressions.append(f"error rate rose {rise:.1%} (allowed {thresholds.max_error_rate_increase:.1%})")

    if baseline.dataset_sha256 != current.dataset_sha256:
        result.warnings.append("dataset differs from the baseline's; added or removed cases are listed separately")
    if result.removed:
        result.warnings.append(f"{len(result.removed)} baseline case(s) missing from the current run")
    for side, run in (("baseline", baseline), ("current", current)):
        if run.capture_content:
            result.warnings.append(
                f"{side} log was made with --capture-content and contains unredacted content; do not commit it"
            )
    flaky = sorted(case_id for case_id, case in current.cases.items() if case.flaky)
    if flaky:
        result.warnings.append(f"{len(flaky)} case(s) passed in some epochs but not all: {', '.join(flaky)}")
    _significance(baseline, current, thresholds, result)
    result.statistics = _statistics(baseline, current)
    return result


BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0  # fixed so the same logs always give the same interval


def _rate(run: RunResults) -> RateInterval:
    passes = sum(c.passed for c in run.cases.values())
    return RateInterval(passes, len(run.cases), *wilson_interval(passes, len(run.cases)))


def _median_change(differences: list[float]) -> MedianChange | None:
    if not differences:
        return None
    estimate, low, high = bootstrap_median_interval(differences, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
    return MedianChange(estimate, low, high, len(differences))


def _case_tokens(case: CaseResult) -> int | None:
    if case.input_tokens is None or case.output_tokens is None:
        return None
    return case.input_tokens + case.output_tokens


def _statistics(baseline: RunResults, current: RunResults) -> Statistics:
    """Pass rates over cases with Wilson and Newcombe intervals, exact McNemar on paired cases, bootstrap medians."""
    before, after = _rate(baseline), _rate(current)
    difference = (
        newcombe_difference_interval(after.passes, after.cases, before.passes, before.cases)
        if before.cases and after.cases
        else None
    )
    pairs = [(baseline.cases[c], current.cases[c]) for c in sorted(set(baseline.cases) & set(current.cases))]
    b = sum(old.passed and not new.passed for old, new in pairs)
    c = sum(not old.passed and new.passed for old, new in pairs)
    latency = [
        new.latency_s - old.latency_s for old, new in pairs if old.latency_s is not None and new.latency_s is not None
    ]
    tokens = [
        float(t_new - t_old)
        for old, new in pairs
        if (t_old := _case_tokens(old)) is not None and (t_new := _case_tokens(new)) is not None
    ]
    return Statistics(
        baseline=before,
        current=after,
        difference=difference,
        paired=len(pairs),
        passed_to_failed=b,
        failed_to_passed=c,
        mcnemar_p=mcnemar_exact_p(b, c),
        latency_s=_median_change(latency),
        tokens=_median_change(tokens),
    )


def _fell(before: tuple[int, int], after: tuple[int, int]) -> bool:
    """Whether the passing share of (passes, runs) fell; cross-multiplied so equal shares compare exactly."""
    return after[0] * before[1] < before[0] * after[1]


def _significance(baseline: RunResults, current: RunResults, thresholds: Thresholds, result: Comparison) -> None:
    """One-sided Fisher tests on shared cases whose pass share fell, then on the pooled epochs of all shared cases.

    A p-value at or below the alpha counts, so 3/3 -> 0/3 (p = 0.05 exactly) is flagged at 0.05.
    """
    shared = sorted(set(baseline.cases) & set(current.cases))
    counts = {
        c: ((baseline.cases[c].passes, baseline.cases[c].runs), (current.cases[c].passes, current.cases[c].runs))
        for c in shared
    }
    if not shared or all(b[1] <= 1 for b, _ in counts.values()) or all(a[1] <= 1 for _, a in counts.values()):
        # Fisher's test says nothing at one epoch a side
        if thresholds.max_p_value is not None:
            result.warnings.append("--max-p-value not applied: needs more than one epoch per case in both runs")
        return
    tests = [(c, b, a) for c, (b, a) in counts.items() if _fell(b, a)]
    pooled_before = (sum(b[0] for b, _ in counts.values()), sum(b[1] for b, _ in counts.values()))
    pooled_after = (sum(a[0] for _, a in counts.values()), sum(a[1] for _, a in counts.values()))
    if len(shared) > 1 and _fell(pooled_before, pooled_after):  # one case pooled would repeat it
        tests.append((f"all {len(shared)} shared cases pooled", pooled_before, pooled_after))  # after the cases
    tested = []
    for label, b, a in tests:
        p = fisher_worse_p(*b, *a)
        shown = f"p={p:.3f}" if p >= 0.001 else "p<0.001"
        tested.append((f"{label} ({b[0]}/{b[1]} -> {a[0]}/{a[1]}, {shown})", p))

    warned = [text for text, p in tested if p <= SIGNIFICANCE_ALPHA + 1e-12]
    if warned:
        result.warnings.append(
            f"pass rate fell significantly (one-sided Fisher p <= {SIGNIFICANCE_ALPHA}): {', '.join(warned)}"
        )
    if thresholds.max_p_value is not None:
        failed = [text for text, p in tested if p <= thresholds.max_p_value + 1e-12]
        if failed:
            result.regressions.append(
                f"pass rate fell with one-sided Fisher p <= {thresholds.max_p_value}: {', '.join(failed)}"
            )


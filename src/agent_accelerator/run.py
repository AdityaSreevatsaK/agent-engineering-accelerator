"""Build and run an evaluation: dataset -> Inspect task -> run directory with log, traces and report."""

from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from fsspec import filesystem
from inspect_ai import Task, eval
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.log import EvalError, EvalLog, read_eval_log, write_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score, Scorer

from agent_accelerator.config import ADAPTERS
from agent_accelerator.dataset import DATASET_FORMAT_VERSION, case_to_metadata, dataset_sha256, load_dataset
from agent_accelerator.judge import JUDGE, SAFE_JUDGE_METADATA, JudgeConfig, judge, judge_provenance, load_golden
from agent_accelerator.scorers import CASE_CHECKS, case_checks, error_type

REDACTED = "[REDACTED]"
# Kept in scrubbed logs: needed for comparison and reports, and free of prompt or output text.
_SAFE_SAMPLE_METADATA = ("agent_error", "usage", "model_id")


def build_task(
    dataset_path: Path,
    agent: str,
    adapter: str = "strands",
    capture_content: bool = False,
    extra_scorers: list[Scorer] | None = None,
    epochs: int = 1,
    judge_config: JudgeConfig | None = None,
    input_map: str | None = None,
    output_map: str | None = None,
    config: str | None = None,
) -> Task:
    """epochs > 1 runs every case that many times, for agents whose results vary between runs.

    judge_config adds the LLM judge as a scorer named "judge"; None leaves the task exactly as without it.
    input_map and output_map ("module:function") adapt a LangGraph graph whose state has no messages channel.
    config is the --config file path, recorded as provenance only.
    """
    if epochs < 1:
        raise ValueError("epochs must be at least 1")
    cases = load_dataset(dataset_path)
    judge_scorers = [_judge_scorer(judge_config, {c.id for c in cases}, capture_content)] if judge_config else []
    samples = [
        Sample(id=c.id, input=c.input, target=c.expected_output or "", metadata=case_to_metadata(c)) for c in cases
    ]
    return Task(
        name=dataset_path.stem,
        dataset=MemoryDataset(samples, name=dataset_path.stem),
        solver=_adapter_solver(adapter, agent, input_map=input_map, output_map=output_map),
        scorer=[case_checks(show_values=capture_content), *(extra_scorers or []), *judge_scorers],
        epochs=epochs,
        metadata={
            "dataset_path": dataset_path.as_posix(),
            "dataset_sha256": dataset_sha256(dataset_path),
            "dataset_format_version": DATASET_FORMAT_VERSION,
            "agent": agent,
            "adapter": adapter,
            **({"config": config} if config else {}),
            **({"input_map": input_map} if input_map else {}),
            **({"output_map": output_map} if output_map else {}),
            "epochs": epochs,
            **({"judge": judge_provenance(judge_config)} if judge_config else {}),
        },
    )


def _judge_scorer(config: JudgeConfig, case_ids: set[str], capture_content: bool) -> Scorer:
    if config.golden_path is not None:
        load_golden(config.golden_path, case_ids)  # fail on unknown ids before the run starts
    golden = config.golden_path.as_posix() if config.golden_path else None
    rubric = config.rubric_path.as_posix() if config.rubric_path else None
    baseline = config.baseline_path.as_posix() if config.baseline_path else None
    return judge(config.model, golden, rubric, show_values=capture_content, baseline_path=baseline)


def _adapter_solver(adapter: str, agent: str, input_map: str | None = None, output_map: str | None = None):
    if (input_map or output_map) and adapter != "langgraph":
        raise ValueError("--input-map and --output-map need --adapter langgraph")
    # Imported lazily: each adapter needs its framework's optional extra installed.
    if adapter == "strands":
        from agent_accelerator.adapters.strands import strands_agent

        return strands_agent(agent=agent)
    if adapter == "langgraph":
        from agent_accelerator.adapters.langgraph import langgraph_agent

        return langgraph_agent(agent=agent, input_map=input_map, output_map=output_map)
    raise ValueError(f"unknown adapter {adapter!r}; available: {', '.join(ADAPTERS)}")


def new_run_dir(runs_dir: Path) -> Path:
    run_dir = runs_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True)
    return run_dir


def run_task(task: Task, run_dir: Path, capture_content: bool, max_samples: int | None = None) -> Path:
    """Runs the task and returns the log path. The agent drives its own model, so Inspect's model is a mock.

    max_samples caps how many cases run at once (None: Inspect's default); live models need it for honest latency.
    """
    if max_samples is not None and max_samples < 1:
        raise ValueError("max_samples must be at least 1")
    # Without capture, Inspect logs to memory and only the scrubbed copy reaches disk, so a run
    # killed part way leaves no payloads behind. Realtime logging would buffer events on disk.
    log_dir = run_dir.as_posix() if capture_content else f"memory://agent-accelerator/{run_dir.name}"
    [log] = eval(
        task,
        model="mockllm/model",
        log_dir=log_dir,
        log_format="json",
        log_realtime=capture_content,
        display="none",
        fail_on_error=False,
        max_samples=max_samples,
        metadata={
            "run_id": run_dir.name,
            "capture_content": capture_content,
            "max_samples": max_samples,
            "accelerator_version": version("agent-accelerator"),
        },
    )
    if capture_content:
        return Path(log.location)
    log_path = run_dir / log.location.rsplit("/", 1)[-1]
    try:
        write_eval_log(scrub(read_eval_log(log.location)), log_path)
    finally:
        filesystem("memory").rm(log_dir, recursive=True)
    return log_path


def scrub(log: EvalLog) -> EvalLog:
    """Removes prompt, output and tool payloads from a log, keeping scores and timings."""
    for sample in log.samples or []:
        sample.input = REDACTED
        sample.target = REDACTED
        sample.messages = []
        sample.output = ModelOutput(model=sample.output.model)
        sample.events = []
        sample.attachments = {}
        sample.store = {}
        sample.metadata = {k: sample.metadata[k] for k in _SAFE_SAMPLE_METADATA if k in sample.metadata}
        if sample.metadata.get("agent_error"):
            sample.metadata["agent_error"] = error_type(sample.metadata["agent_error"])
        # Exception messages and tracebacks can quote prompts or tool payloads.
        if sample.error:
            sample.error = EvalError(message=REDACTED, traceback=REDACTED, traceback_ansi=REDACTED)
        for name, score in (sample.scores or {}).items():
            _scrub_score(score, name)
    if log.error:
        log.error = EvalError(message=REDACTED, traceback=REDACTED, traceback_ansi=REDACTED)
    # Reductions repeat each sample's scores, including any answer a custom scorer recorded.
    for reduction in log.reductions or []:
        for sample_score in reduction.samples:
            _scrub_score(sample_score, reduction.scorer)
    return log


def _scrub_score(score: Score, scorer: str) -> None:
    score.answer = None
    score.history = []  # earlier edits keep their own answers and explanations
    # case_checks and judge redact their own explanations; a custom scorer's other fields may quote output.
    if scorer == JUDGE:
        score.metadata = {k: v for k, v in (score.metadata or {}).items() if k in SAFE_JUDGE_METADATA}
    elif scorer != CASE_CHECKS:
        score.explanation = None
        score.reason = None
        score.metadata = None

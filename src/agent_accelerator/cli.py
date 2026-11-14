"""Command line: aea init | run | compare | report | check | export.

Exit codes: 0 success, 1 regression detected, 2 usage or run error.
"""

import argparse
import keyword
import shutil
import sys
from importlib.resources import files
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING

from agent_accelerator.config import ADAPTERS, ConfigError, load_config

if TYPE_CHECKING:
    from agent_accelerator.judge import JudgeConfig
    from agent_accelerator.trace_summary import TraceSummary

EXIT_OK, EXIT_REGRESSION, EXIT_ERROR = 0, 1, 2
TEMPLATE_FILES = ("agent.py", "dataset.jsonl")


def _init(args: argparse.Namespace) -> int:
    target: Path = args.dir
    # Do not write through linked directories or templates. In particular,
    # --force must never truncate files outside the requested target directory.
    # Preflight *both* template names before writing either, to avoid partial edits.
    if any(path.is_symlink() for path in (target, *target.parents)):
        raise ValueError(f"{target.as_posix()} traverses a symlink; refusing to initialise")
    if target.is_dir():
        linked = [name for name in TEMPLATE_FILES if (target / name).is_symlink()]
        if linked:
            raise ValueError(
                f"{target.as_posix()} contains linked template file(s): "
                f"{', '.join(linked)}; refusing to overwrite"
            )
    if target.exists() and not target.is_dir():
        raise ValueError(f"{target.as_posix()} exists and is not a directory")
    if target.is_dir() and any(target.iterdir()) and not args.force:
        raise ValueError(f"{target.as_posix()} is not empty; use --force to overwrite agent.py and dataset.jsonl in it")
    template = files("agent_accelerator").joinpath("template")
    contents = {name: template.joinpath(name).read_text(encoding="utf-8") for name in TEMPLATE_FILES}
    target.mkdir(parents=True, exist_ok=True)
    for name, text in contents.items():
        (target / name).write_text(text, encoding="utf-8", newline="\n")

    module = _module_path(target)
    shown = target.as_posix()
    print(f"Created {shown}/agent.py and {shown}/dataset.jsonl. Next:")
    print(f"  1. Edit agent.py (tool, prompt, model) and dataset.jsonl (one case per behaviour) in {shown}/")
    agent = f"{module}:build_agent" if module else "<module>.agent:build_agent"
    print(f"  2. uv run aea run {shown}/dataset.jsonl --agent {agent} --epochs 3 --max-samples 4")
    if module is None:
        print(
            f"note: {shown} is outside the current directory or not a valid Python module path; "
            "it must be importable from the directory you run aea in"
        )
    return EXIT_OK


def _module_path(target: Path) -> str | None:
    """Dotted import path of target/agent.py relative to the working directory, or None if not importable."""
    try:
        parts = target.resolve().relative_to(Path.cwd().resolve()).parts
    except ValueError:
        return None
    if not all(part.isidentifier() and not keyword.iskeyword(part) for part in parts):
        return None
    return ".".join((*parts, "agent"))


def _doctor(args: argparse.Namespace) -> int:
    """Check local inputs and importability without executing agent factories or creating run artefacts.

    Importing a user module executes its top-level Python statements, so only
    run this with trusted application code. No agent factory or scorer is called.
    """
    from agent_accelerator.adapters import load_factory
    from agent_accelerator.dataset import load_dataset

    cases = load_dataset(args.dataset)
    references = [("agent", args.agent)]
    references += [(name.replace("_", "-"), getattr(args, name)) for name in ("input_map", "output_map")]
    references += [("scorer", ref) for ref in args.scorer]
    for label, reference in references:
        if reference is not None:
            load_factory(reference)
            print(f"OK {label}: {reference}")
    print(f"OK dataset: {len(cases)} valid case(s); adapter: {args.adapter}")
    if args.adapter == "langgraph":
        if args.input_map is None:
            print(
                "note: graphs without a 'messages' state channel need --input-map module:function",
                file=sys.stderr,
            )
        if args.output_map is None:
            print(
                "note: graphs without an AI message or structured_response need --output-map module:function",
                file=sys.stderr,
            )
    print("PASS: preflight complete; no agent factory, evaluation, or model was executed by AEA")
    return EXIT_OK


def _run(args: argparse.Namespace) -> int:
    return _execute_run(args)[0]


def _execute_run(args: argparse.Namespace) -> tuple[int, Path]:
    """Runs the dataset, prints the run summary, and returns the exit code and the new run directory."""
    # Order matters: tracing must be configured before the adapter imports the framework.
    from agent_accelerator.report import validate_prices
    from agent_accelerator.run import new_run_dir

    validate_prices(args.input_price, args.output_price)  # fail before spending on a run
    judge_config = _judge_config(args)
    run_dir = new_run_dir(args.runs_dir)
    from agent_accelerator.tracing import configure_tracing

    provider = configure_tracing(run_dir / "traces.jsonl", args.capture_content)
    from agent_accelerator.adapters import load_factory
    from agent_accelerator.compare import load_results
    from agent_accelerator.report import render_case_lines, render_run
    from agent_accelerator.run import build_task, run_task

    try:
        scorers = [load_factory(ref)() for ref in args.scorer]
        task = build_task(
            args.dataset,
            args.agent,
            args.adapter,
            args.capture_content,
            extra_scorers=scorers,
            epochs=args.epochs,
            judge_config=judge_config,
            input_map=args.input_map,
            output_map=args.output_map,
            config=args.config.as_posix() if args.config else None,
        )
        log_path = run_task(task, run_dir, args.capture_content, args.max_samples)
    except BaseException:
        # Nothing usable was written, and a log that failed mid-scrub may still hold payloads.
        provider.shutdown()
        shutil.rmtree(run_dir, ignore_errors=True)
        raise
    provider.shutdown()
    results = load_results(log_path)
    report_path = run_dir / "report.md"
    report_path.write_text(render_run(results, _traces(run_dir), args.input_price, args.output_price), encoding="utf-8")
    passed = sum(c.passed for c in results.cases.values())
    print(f"{run_dir.as_posix()}  status={results.status}  passed={passed}/{len(results.cases)}")
    for line in render_case_lines(results):
        print(line)
    if passed < len(results.cases) and not args.capture_content:
        hint = "failure values are redacted; rerun with --capture-content to see them (do not commit that log)"
        print(f"hint: {hint}", file=sys.stderr)
    print(f"report: {report_path.as_posix()}")
    return (EXIT_OK if results.status == "success" else EXIT_ERROR), run_dir


def _judge_config(args: argparse.Namespace) -> "JudgeConfig | None":
    from agent_accelerator.judge import JudgeConfig

    if args.judge is None:
        if args.golden or args.judge_rubric or args.judge_baseline:
            raise ValueError("--golden, --judge-rubric and --judge-baseline need --judge MODEL")
        return None
    if args.golden and args.judge_baseline:
        raise ValueError("--golden and --judge-baseline cannot be combined: choose a reference or a baseline run")
    if args.judge_baseline:
        _check_judge_baseline(args.judge_baseline, args.dataset)
    _check_judge_files(args.golden, args.judge_rubric, args.dataset)
    return JudgeConfig(args.judge, args.golden, args.judge_rubric, args.judge_baseline)


def _check_judge_files(golden_path: Path | None, rubric_path: Path | None, dataset: Path) -> None:
    """Fails on an unusable golden or rubric file before the run directory exists."""
    from agent_accelerator.dataset import load_dataset
    from agent_accelerator.judge import load_golden, load_rubric

    if golden_path is not None:
        load_golden(golden_path, {c.id for c in load_dataset(dataset)})
    if rubric_path is not None:
        load_rubric(rubric_path)


def _check_judge_baseline(baseline_path: Path, dataset: Path) -> None:
    """Fails on an unusable baseline before the run directory exists; warns when its dataset may differ."""
    from agent_accelerator.dataset import dataset_sha256
    from agent_accelerator.judge import baseline_dataset_warning, load_baseline

    warning = baseline_dataset_warning(load_baseline(baseline_path), dataset_sha256(dataset))
    if warning:
        print(f"warning: {warning}", file=sys.stderr)


def _compare(args: argparse.Namespace) -> int:
    regressed, text = _comparison(args.baseline, args.current, args)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return EXIT_REGRESSION if regressed else EXIT_OK


def _comparison(baseline_path: Path, current_path: Path, args: argparse.Namespace) -> tuple[bool, str]:
    """Compares two runs with the threshold flags in args; returns whether it regressed and the Markdown report."""
    from agent_accelerator.compare import Thresholds, compare, load_results
    from agent_accelerator.report import render_comparison

    thresholds = Thresholds(
        args.max_new_failures, args.max_pass_rate_drop, args.max_error_rate_increase, args.max_p_value
    )
    baseline = load_results(baseline_path, args.min_case_pass_rate)
    cmp = compare(baseline, load_results(current_path, args.min_case_pass_rate), thresholds)
    return cmp.regressed, render_comparison(cmp)


def _check(args: argparse.Namespace) -> int:
    """Runs the dataset, then freezes the run as the baseline or compares it against the baseline."""
    baseline: Path = args.baseline
    if args.update_baseline:
        _validate_baseline_target(baseline, args.runs_dir, args.capture_content)
    elif not baseline.exists():
        raise FileNotFoundError(f"no baseline at {baseline.as_posix()}; run with --update-baseline first")

    code, run_dir = _execute_run(args)
    if code != EXIT_OK:
        print(f"ERROR run did not succeed: {run_dir.as_posix()}")
        return EXIT_ERROR
    if args.update_baseline:
        from agent_accelerator.baseline import freeze_run_as_baseline

        previous = freeze_run_as_baseline(
            run_dir, baseline, args.runs_dir, args.capture_content, _validate_baseline_target
        )
        print(f"BASELINE frozen: {baseline.as_posix()} from {run_dir.as_posix()}")
        if previous is not None:
            print(f"BASELINE previous version retained: {previous.as_posix()}")
        return EXIT_OK

    regressed, text = _comparison(baseline, run_dir, args)
    comparison_path = run_dir / "comparison.md"
    comparison_path.write_text(text, encoding="utf-8")
    verdict = "REGRESSION" if regressed else "OK"
    print(
        f"{verdict}: baseline {baseline.as_posix()}  run {run_dir.as_posix()}  comparison {comparison_path.as_posix()}"
    )
    return EXIT_REGRESSION if regressed else EXIT_OK


def _validate_baseline_target(baseline: Path, runs_dir: Path, capture_content: bool) -> None:
    """Refuses a baseline that would hold unredacted content, or a path that is unsafe to replace."""
    from inspect_ai.log import read_eval_log

    from agent_accelerator.compare import resolve_log

    if capture_content:
        raise ValueError("--update-baseline cannot be combined with --capture-content: a baseline must be redacted")
    if any(part.is_symlink() for part in (baseline, *baseline.parents)):
        raise ValueError(f"--baseline {baseline.as_posix()} traverses a symlink; refusing to replace it")
    if runs_dir.resolve().is_relative_to(baseline.resolve()):
        raise ValueError(f"--baseline {baseline.as_posix()} contains --runs-dir {runs_dir.as_posix()}")
    if not baseline.exists() or (baseline.is_dir() and not any(baseline.iterdir())):
        return
    if not baseline.is_dir():
        raise ValueError(f"--baseline {baseline.as_posix()} exists and is not a run directory")
    try:
        log_path = resolve_log(baseline)
    except FileNotFoundError:
        raise ValueError(f"--baseline {baseline.as_posix()} is not a run directory; refusing to replace it") from None

    # A directory with one arbitrary .json file must not qualify for recursive
    # deletion. Only a parsed Inspect log and standard run artefacts may be
    # replaced. Reject linked files, subdirectories and user-added documents.
    allowed = {log_path.name, "report.md", "comparison.md", "traces.jsonl"}
    unexpected = sorted(
        entry.name
        for entry in baseline.iterdir()
        if entry.name not in allowed or entry.is_symlink() or not entry.is_file()
    )
    if unexpected:
        raise ValueError(
            f"--baseline {baseline.as_posix()} has unrelated or linked files "
            f"({', '.join(unexpected)}); refusing to replace it"
        )
    try:
        log = read_eval_log(log_path)
    except Exception:
        raise ValueError(
            f"--baseline {baseline.as_posix()} has no valid Inspect eval log; refusing to replace it"
        ) from None
    # A valid Inspect JSON log is not necessarily a privacy-safe AEA baseline.
    # Refuse obvious raw payloads rather than preserving them in hidden backups.
    # Score provenance and user-controlled identifiers still require review.
    from agent_accelerator.run import REDACTED

    metadata = log.eval.metadata or {}
    if metadata.get("capture_content") is True or (log.metadata or {}).get("capture_content") is True:
        raise ValueError(f"--baseline {baseline.as_posix()} records captured content; refusing to replace it")
    for sample in log.samples or []:
        if (
            sample.input != REDACTED
            or sample.target != REDACTED
            or sample.messages
            or sample.events
            or sample.attachments
            or sample.store
            or sample.output.completion
            or sample.output.choices
        ):
            raise ValueError(
                f"--baseline {baseline.as_posix()} contains unredacted sample content; refusing to replace it"
            )


def _report(args: argparse.Namespace) -> int:
    from agent_accelerator.compare import load_results
    from agent_accelerator.report import render_run

    traces = _traces(args.run if args.run.is_dir() else args.run.parent)
    print(render_run(load_results(args.run), traces, args.input_price, args.output_price))
    return EXIT_OK


def _backups(args: argparse.Namespace) -> int:
    """List retained previous AEA baselines without modifying or reading their contents."""
    from agent_accelerator.baseline import retained_backup_paths

    backups = retained_backup_paths(args.baseline)
    if not backups:
        print(f"No retained AEA baseline backups found for {args.baseline.as_posix()}")
    else:
        print(f"Retained AEA baseline backups for {args.baseline.as_posix()}:")
        for previous in backups:
            print(f"  {previous.as_posix()}")
    print("Read-only inventory. Nothing was removed; review retention and access before cleanup.")
    return EXIT_OK


def _export(args: argparse.Namespace) -> int:
    from agent_accelerator.export import BrowserError, export_report

    try:
        path = export_report(args.report, args.format, args.output)
    except BrowserError as exc:
        print(f"error: {exc}; try --format html", file=sys.stderr)
        return EXIT_ERROR
    print(path.as_posix())
    return EXIT_OK


def _traces(run_dir: Path) -> "list[TraceSummary] | None":
    from agent_accelerator.trace_summary import summarise_traces

    path = run_dir / "traces.jsonl"
    return summarise_traces(path) if path.exists() else None


def _add_price_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-price", type=float, help="USD per million input tokens, for an estimated cost")
    parser.add_argument("--output-price", type=float, help="USD per million output tokens, for an estimated cost")


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("dataset", type=Path, help="JSONL dataset file")
    parser.add_argument(
        "--config",
        type=Path,
        metavar="FILE",
        help="TOML file setting adapter, agent, input_map and output_map; flags given on the command line win",
    )
    parser.add_argument("--agent", help="agent factory as module:function (required, here or in --config)")
    parser.add_argument("--adapter", choices=ADAPTERS, help="default: strands")
    parser.add_argument(
        "--input-map",
        metavar="MODULE:FUNCTION",
        help="langgraph only: function turning the question into the graph's input dict (for state with no messages)",
    )
    parser.add_argument(
        "--output-map",
        metavar="MODULE:FUNCTION",
        help="langgraph only: function turning the final graph state into the answer string",
    )
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--capture-content", action="store_true", help="keep prompts, outputs and tool payloads")
    parser.add_argument("--epochs", type=int, default=1, help="run each case N times (for live models)")
    parser.add_argument("--max-samples", type=int, help="run at most N cases at once (default: Inspect's limit)")
    parser.add_argument(
        "--scorer",
        action="append",
        default=[],
        help="extra Inspect scorer as module:function (repeatable); a case passes only if every scorer passes",
    )
    parser.add_argument(
        "--judge",
        metavar="MODEL",
        help="add an LLM judge scorer using this Inspect model, e.g. bedrock/us.anthropic.claude-haiku-5-5 "
        "(mockllm/aea-judge-double: offline double)",
    )
    parser.add_argument(
        "--golden", type=Path, metavar="FILE", help="JSONL reference answers by case id for the judge (needs --judge)"
    )
    parser.add_argument(
        "--judge-rubric",
        type=Path,
        metavar="FILE",
        help="JSON list of judge criteria (default: built-in rubric; none with --judge-baseline)",
    )
    parser.add_argument(
        "--judge-baseline",
        type=Path,
        metavar="RUN",
        help="judge each answer against this run's answer (run directory or log made with --capture-content; "
        "needs --judge, not with --golden)",
    )
    _add_price_args(parser)


def _add_threshold_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-new-failures", type=_nonnegative_int, default=0)
    parser.add_argument("--max-pass-rate-drop", type=_rate, default=0.0, help="fraction, e.g. 0.05")
    parser.add_argument("--max-error-rate-increase", type=_rate, default=0.0, help="fraction, e.g. 0.05")
    parser.add_argument(
        "--min-case-pass-rate",
        type=_positive_rate,
        default=1.0,
        help="share of epochs a case must pass to count as passing, e.g. 0.8 (default 1.0: every epoch)",
    )
    parser.add_argument(
        "--max-p-value",
        type=_alpha,
        metavar="ALPHA",
        help="regress when a case's or the pooled pass rate fell with one-sided Fisher p <= ALPHA, e.g. 0.05",
    )


def _nonnegative_int(value: str) -> int:
    """Non-negative case count for regression gates."""
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a non-negative integer, got {value!r}") from None
    if count < 0:
        raise argparse.ArgumentTypeError(f"must be a non-negative integer, got {value!r}")
    return count


def _rate(value: str) -> float:
    """Finite proportion in [0, 1]; NaN must not silently disable a regression gate."""
    try:
        rate = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a number between 0 and 1, got {value!r}") from None
    if not isfinite(rate) or not 0 <= rate <= 1:
        raise argparse.ArgumentTypeError(f"must be a finite number between 0 and 1, got {value!r}")
    return rate


def _positive_rate(value: str) -> float:
    rate = _rate(value)
    if rate == 0:
        raise argparse.ArgumentTypeError("must be greater than 0 and at most 1")
    return rate


def _alpha(value: str) -> float:
    """A significance level strictly between 0 and 1; argparse turns the error into exit code 2."""
    try:
        alpha = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from None
    if not 0 < alpha < 1:
        raise argparse.ArgumentTypeError(f"must be between 0 and 1 exclusive, got {value}")
    return alpha


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aea", description="Agent evaluation and regression checks.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create an agent folder from the template")
    init.add_argument("dir", type=Path, help="folder to create (parents allowed)")
    init.add_argument("--force", action="store_true", help="overwrite agent.py and dataset.jsonl in a non-empty folder")
    init.set_defaults(func=_init)

    doctor = sub.add_parser("doctor", help="check dataset, config and factory imports without evaluating agents")
    doctor.add_argument("dataset", type=Path, help="JSONL dataset to validate without evaluating")
    doctor.add_argument("--config", type=Path, metavar="FILE", help="TOML adapter/agent/mapping settings")
    doctor.add_argument("--agent", help="agent factory as module:function (or supply via --config)")
    doctor.add_argument("--adapter", choices=ADAPTERS, help="default: strands")
    doctor.add_argument("--input-map", metavar="MODULE:FUNCTION", help="LangGraph input mapper to import-check")
    doctor.add_argument("--output-map", metavar="MODULE:FUNCTION", help="LangGraph output mapper to import-check")
    doctor.add_argument("--scorer", action="append", default=[], help="custom scorer to import-check (repeatable)")
    doctor.set_defaults(func=_doctor)

    run = sub.add_parser("run", help="run an agent against a dataset")
    _add_run_args(run)
    run.set_defaults(func=_run)

    cmp = sub.add_parser("compare", help="compare a run against a baseline")
    cmp.add_argument("baseline", type=Path, help="baseline run directory or log file")
    cmp.add_argument("current", type=Path, help="current run directory or log file")
    _add_threshold_args(cmp)
    cmp.add_argument("--output", type=Path, help="also write the Markdown report here")
    cmp.set_defaults(func=_compare)

    rep = sub.add_parser("report", help="print the Markdown report for a run")
    rep.add_argument("run", type=Path, help="run directory or log file")
    _add_price_args(rep)
    rep.set_defaults(func=_report)

    backups = sub.add_parser("backups", help="list retained previous baselines without deleting them")
    backups.add_argument("baseline", type=Path, help="active baseline directory whose prior copies to inspect")
    backups.set_defaults(func=_backups)

    chk = sub.add_parser("check", help="run a dataset and compare it against a baseline run directory")
    _add_run_args(chk)
    chk.add_argument("--baseline", type=Path, required=True, help="baseline run directory")
    chk.add_argument(
        "--update-baseline", action="store_true", help="replace the baseline with this run instead of comparing"
    )
    _add_threshold_args(chk)
    chk.set_defaults(func=_check)

    exp = sub.add_parser("export", help="export a Markdown report to a self-contained HTML file or PDF")
    exp.add_argument("report", type=Path, help="report Markdown file (report.md or a compare --output file)")
    exp.add_argument("--format", choices=["html", "pdf"], default="pdf", help="output format (default: pdf)")
    exp.add_argument("--output", type=Path, help="output file (default: next to the report, with the new extension)")
    exp.set_defaults(func=_export)
    return parser


def _apply_config(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Fills run settings left unset on the command line from --config, then the built-in defaults."""
    if args.config is not None:
        config = load_config(args.config)
        for key, value in config.items():
            if getattr(args, key) is None:
                setattr(args, key, value)
    if args.adapter is None:
        args.adapter = "strands"
    if args.agent is None:
        parser.error("--agent is required (flag or config)")
    # Syntax-check selected references before allocating a run directory,
    # including flags that override a valid TOML value. No user code is imported.
    from agent_accelerator.adapters import validate_factory_reference

    for key in ("agent", "input_map", "output_map", "scorer"):
        references = args.scorer if key == "scorer" else [getattr(args, key)]
        for ref in references:
            if ref is None:
                continue
            try:
                validate_factory_reference(ref)
            except ValueError as exc:
                raise ConfigError(f"--{key.replace('_', '-')}: {exc}") from None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "config"):
        try:
            _apply_config(parser, args)
        except ConfigError as exc:
            # A malformed or unreadable config is a run error (return code 2),
            # not an argparse usage exception. Reject it before any run exists.
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
    if (getattr(args, "input_map", None) or getattr(args, "output_map", None)) and args.adapter != "langgraph":
        parser.error("--input-map and --output-map need --adapter langgraph")  # exits with code 2
    sys.path.insert(0, str(Path.cwd()))  # agent factories are resolved relative to the working directory
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())

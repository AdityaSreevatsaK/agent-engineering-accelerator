"""Audit current AEA acceptance claims against executable source contracts.

This is a new, dependency-free assessment of reconstructed code. It does not
rewrite the provisional historical acceptance/review files, invoke any agent
or certify video-byte fidelity, security approval or production readiness.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PKG = Path("src/agent_accelerator")
COMMANDS = frozenset({"init", "run", "compare", "report", "check", "export"})
SUPPORTED_ADAPTERS = frozenset({"strands", "langgraph"})
CONFIG_FIELDS = frozenset({"adapter", "agent", "input_map", "output_map"})
REQUIRED_TASK_METADATA = frozenset({
    "dataset_path", "dataset_sha256", "dataset_format_version",
    "agent", "adapter", "epochs",
})
REQUIRED_RUN_METADATA = frozenset({
    "run_id", "capture_content", "max_samples", "accelerator_version",
})
REQUIRED_SCRUBBED_FIELDS = frozenset({
    "input", "target", "messages", "output", "events",
    "attachments", "store", "metadata",
})
REQUIRED_FLAGS = frozenset({
    "--capture-content", "--config", "--max-samples", "--epochs",
    "--min-case-pass-rate", "--input-map", "--output-map",
    "--judge", "--max-new-failures", "--max-pass-rate-drop",
})
UNIMPLEMENTED_GATES = frozenset({"--max-latency", "--max-cost"})
# The historical D11 assertion mentions config content, source revision and
# dependency/library versions; those are NOT the same as config path or the
# accelerator distribution version. If they appear, re-evaluate D11.
MISSING_D11_EVIDENCE = (
    "configuration_file_content_sha256",
    "git_source_revision",
    "python_and_dependency_versions",
)


def parsed(root: Path, source: str) -> ast.Module:
    path = root / PKG / source
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))


def named_function(module: ast.Module, name: str) -> ast.FunctionDef:
    functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(functions) != 1:
        raise ValueError(f"Expected one source definition of {name}, got {len(functions)}")
    return functions[0]


def calls_named(func: ast.FunctionDef, name: str) -> list[ast.Call]:
    return [
        node for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == name
    ]


def string_keys(node: ast.expr) -> set[str]:
    # Optional metadata keys appear inside conditional dict unpackings
    # such as **({"config": config} if config else {}).
    return {
        key.value
        for child in ast.walk(node) if isinstance(child, ast.Dict)
        for key in child.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def metadata_keys(module: ast.Module, function: str, call_name: str) -> set[str]:
    fn = named_function(module, function)
    calls = calls_named(fn, call_name)
    meta = [
        kw.value
        for call in calls for kw in call.keywords
        if kw.arg == "metadata"
    ]
    if len(meta) != 1:
        raise ValueError(f"{function}: expected one {call_name} metadata expression, got {len(meta)}")
    return string_keys(meta[0])


def assigned_strings(module: ast.Module, name: str) -> set[str]:
    matches = [
        n.value for n in module.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
    ]
    if len(matches) != 1 or not isinstance(matches[0], (ast.Tuple, ast.List)):
        raise ValueError(f"{name}: expected one literal tuple/list of settings")
    items = matches[0].elts
    if not all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in items):
        raise ValueError(f"{name}: expected string settings")
    return {x.value for x in items}


def parser_contract(module: ast.Module) -> tuple[set[str], set[str]]:
    commands: set[str] = set()
    options: set[str] = set()
    for n in ast.walk(named_function(module, "build_parser")):
        if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Attribute):
            continue
        if n.func.attr == "add_parser":
            if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                commands.add(n.args[0].value)
    # Options also appear in _add_run_args and _add_threshold_args, so
    # inspect all add_argument() calls in the source, not build_parser alone.
    for n in ast.walk(module):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_argument":
            options.update(
                arg.value for arg in n.args
                if isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and arg.value.startswith("--")
            )
    return commands, options


def normalises_line_endings(module: ast.Module) -> bool:
    fn = named_function(module, "dataset_sha256")
    has_sha = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "hashlib" and n.func.attr == "sha256"
        for n in ast.walk(fn)
    )
    normalises = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "replace"
        and len(n.args) >= 2
        and isinstance(n.args[0], ast.Constant) and n.args[0].value == b"\r\n"
        and isinstance(n.args[1], ast.Constant) and n.args[1].value == b"\n"
        for n in ast.walk(fn)
    )
    return has_sha and normalises


def scrub_assignments(module: ast.Module) -> set[str]:
    result: set[str] = set()
    for n in ast.walk(named_function(module, "scrub")):
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id == "sample":
                        result.add(target.attr)
    return result


def assess(root: Path = ROOT) -> dict:
    run = parsed(root, "run.py")
    cli = parsed(root, "cli.py")
    config = parsed(root, "config.py")
    dataset = parsed(root, "dataset.py")
    task_meta = metadata_keys(run, "build_task", "Task")
    run_meta = metadata_keys(run, "run_task", "eval")
    commands, options = parser_contract(cli)
    adapters = assigned_strings(config, "ADAPTERS")
    config_keys = assigned_strings(config, "CONFIG_KEYS")
    scrub_fields = scrub_assignments(run)
    issues = []
    for name, expected, actual in (
        ("CLI commands", COMMANDS, commands),
        ("adapter names", SUPPORTED_ADAPTERS, adapters),
        ("TOML config keys", CONFIG_FIELDS, config_keys),
        ("Task metadata", REQUIRED_TASK_METADATA, task_meta),
        ("run metadata", REQUIRED_RUN_METADATA, run_meta),
        ("CLI capabilities", REQUIRED_FLAGS, options),
        ("sample scrub fields", REQUIRED_SCRUBBED_FIELDS, scrub_fields),
    ):
        missing = expected - actual
        if missing:
            issues.append(f"{name}: missing {', '.join(sorted(missing))}")
    if options & UNIMPLEMENTED_GATES:
        issues.append("Historical D9 no-gates assessment requires review: a cost/latency gate was introduced")
    crlf = normalises_line_endings(dataset)
    if not crlf:
        issues.append("Historical D20 line-ending-normalised dataset SHA256 no longer established")
    optional_task = task_meta - REQUIRED_TASK_METADATA
    # Record facts rather than guessing that a config path is a config digest.
    features = {
        "CLI": {"commands": sorted(commands), "flags": sorted(options)},
        "configuration": {"supported_adapters": sorted(adapters), "toml_keys": sorted(config_keys)},
        "provenance": {
            "task_metadata_keys": sorted(task_meta),
            "run_metadata_keys": sorted(run_meta),
            "optional_task_metadata": sorted(optional_task),
            "dataset_sha256_normalises_crlf": crlf,
            "config_content_hash_found": "config_sha256" in task_meta or "config_hash" in task_meta,
            "git_revision_found": bool({"git_sha", "git_revision", "source_revision", "commit_sha"} & (task_meta | run_meta)),
            "dependency_versions_found": bool({"dependency_versions", "package_versions", "runtime_versions"} & (task_meta | run_meta)),
        },
        "privacy": {
            "capture_flag": "--capture-content" in options,
            "sample_scrubbed_fields": sorted(scrub_fields),
            "explicit_baseline_opt_in_guard": "--update-baseline" in options,
        },
        "historical_acceptance_reassessment": {
            "D4_redaction": "source-supported; runtime/privacy CI evidence is separate",
            "D9_latency_cost_blocking_gates": "partly met (informational, no CLI latency/cost gates)"
                if not options & UNIMPLEMENTED_GATES else "re-review required",
            "D11_reproducible_provenance": "partly verified",
            "D20_crlf_dataset_hash": "source-supported" if crlf else "source contract broken",
            "D21_concurrency_metadata": "source-supported"
                if "--max-samples" in options and "max_samples" in run_meta else "source contract broken",
        },
        "unverified_by_this_tool": [
            *MISSING_D11_EVIDENCE,
            "human_source_video_byte_fidelity",
            "provider_level_runtime_variance",
            "production_security_and_release_approval",
        ],
    }
    # Automatically downgrade or trigger review if D11 fields are added;
    # source additions are not proof they are populated correctly in real logs.
    prov = features["provenance"]
    if any(prov[k] for k in (
        "config_content_hash_found", "git_revision_found", "dependency_versions_found",
    )):
        features["historical_acceptance_reassessment"]["D11_reproducible_provenance"] = "re-review required"

    return {
        "assessment_scope": "reconstructed source contract; not video originals or production",
        "checks_pass": not issues,
        "issues": issues,
        **features,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--format", choices=("text", "json"), default="text")
    args = p.parse_args(argv)
    try:
        report = assess(args.root)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"AEA acceptance reconciliation ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("AEA acceptance source audit: "+("PASS" if report["checks_pass"] else "FAIL"))
        for k, status in report["historical_acceptance_reassessment"].items():
            print(f"  {k}: {status}")
        for issue in report["issues"]:
            print(f"  ISSUE: {issue}")
        print("Source contracts are NOT equivalent to original video, security signoff or release acceptance.")
    return 0 if report["checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

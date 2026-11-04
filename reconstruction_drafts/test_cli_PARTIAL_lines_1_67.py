import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.scorer import CORRECT

import agent_accelerator.cli as cli_module
from agent_accelerator.cli import build_parser, main

REPO = Path(__file__).parents[2]
DATASET = REPO / "examples" / "calculator" / "dataset.jsonl"
AGENT = "examples.calculator.agent:build_agent"
FIXTURE = REPO / "tests" / "fixtures" / "calculator_capture_content.json"
BROKEN_FIXTURE = REPO / "tests" / "fixtures" / "calculator_broken_redacted.json"
TRACE_HEADER = "## Trace summary (informational)"
INPUT_TEXT = "What is 2 plus 3?"
# Replaced in the runs fixture by a dataset with one passing and two failing cases. The failing ids sort
# after the passing one, so failing-first order is not alphabetical order. "4|2" puts a pipe in the reason.
FAILING_DATASET = "<failing dataset>"
FAILING_CASES = [
    {"id": "a_pass", "input": "What is 2 plus 3?", "expected_output": "5"},
    {"id": "y_fail", "input": "What is 6 times 7?", "expected_output": "4|2"},
    {"id": "z_fail", "input": "What is 9 minus 4?", "expected_output": "6"},
]

# Every `run` goes through a subprocess: the tracer provider can only be set once per process.
# All runs start together in one module fixture, since each takes several seconds.
RUNS = {
    "good": [str(DATASET), "--agent", AGENT],
    "capture": [str(DATASET), "--agent", AGENT, "--capture-content"],
    "no_colon": [str(DATASET), "--agent", "examples.calculator.agent.build_agent"],
    "unknown_module": [str(DATASET), "--agent", "examples.calculator.no_such_module:build_agent"],
    "unknown_function": [str(DATASET), "--agent", "examples.calculator.agent:no_such_function"],
    "missing_dataset": [str(REPO / "examples" / "calculator" / "no_such_dataset.jsonl"), "--agent", AGENT],
    "epochs_0": [str(DATASET), "--agent", AGENT, "--epochs", "0"],
    "max_samples_0": [str(DATASET), "--agent", AGENT, "--max-samples", "0"],
    "eval_error": [str(DATASET), "--agent", "aea_cli_doubles:fatal_factory"],
    "failing": [FAILING_DATASET, "--agent", AGENT],
    "failing_capture": [FAILING_DATASET, "--agent", AGENT, "--capture-content"],
    "failing_epochs": [FAILING_DATASET, "--agent", AGENT, "--epochs", "2"],
    "half_passing": [str(DATASET), "--agent", AGENT, "--epochs", "2", "--scorer", "aea_cli_doubles:first_epoch_only"],
    "custom_scorer": [str(DATASET), "--agent", AGENT, "--scorer", "aea_cli_doubles:always_wrong"],
    "custom_scorer_capture": [
        *[str(DATASET), "--agent", AGENT, "--capture-content"],
        *["--scorer", "aea_cli_doubles:always_wrong"],
    ],
    "two_scorers": [
        *[str(DATASET), "--agent", AGENT],
        *["--scorer", "aea_cli_doubles:always_right", "--scorer", "aea_cli_doubles:always_wrong"],
    ],
    "scorer_no_colon": [str(DATASET), "--agent", AGENT, "--scorer", "aea_cli_doubles.always_wrong"],
    "scorer_missing_attribute": [str(DATASET), "--agent", AGENT, "--scorer", "aea_cli_doubles:no_such_scorer"],
}
HINT = "hint: failure values are redacted; rerun with --capture-content to see them (do not commit that log)"
BAD_RUNS = [
    *["no_colon", "unknown_module", "unknown_function", "missing_dataset", "epochs_0", "max_samples_0"],
    *["scorer_no_colon", "scorer_missing_attribute"],
]
CUSTOM_EXPLANATION = "custom scorer saw the output"

# A BaseException that is not an Exception escapes the adapter's per-case handling, so Inspect ends
# the eval with status "error" after the run dir and log already exist.

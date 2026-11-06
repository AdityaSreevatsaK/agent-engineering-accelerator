"""Exercise seven original comparison cases accidentally marked 'slow'.

The recovered tests/conftest.py recognises three fixture *names* as
subprocess fixtures, but pytest also includes direct parametrisation names
in fixturenames. The original source-recorded compare test uses a numeric
parametrisation called `runs` and performs no subprocess or model call.

Preserve the recovered historical conftest/test source unchanged.
Execute these seven test cases in a distinct offline lane, while verifying
their exact source structure so the selection cannot silently drift.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPARE = ROOT / "tests" / "unit" / "test_compare.py"
CONFTEST = ROOT / "tests" / "conftest.py"
TEST_NAME = "test_case_is_flaky_only_when_some_but_not_all_epochs_passed"
EXPECTED_NAMES = ("runs", "passes", "flaky")
EXPECTED_ROWS = (
    (4, 2, True),
    (4, 1, True),
    (4, 3, True),
    (4, 4, False),
    (4, 0, False),
    (1, 1, False),
    (1, 0, False),
)


def assert_source_contract() -> int:
    source = COMPARE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=COMPARE.as_posix(), feature_version=(3, 11))
    tests = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TEST_NAME]
    if len(tests) != 1:
        raise AssertionError("Original parameter-collision comparison test missing or duplicated")
    [test] = tests
    if tuple(arg.arg for arg in test.args.args) != EXPECTED_NAMES:
        raise AssertionError("Unexpected change in original comparison test parameters")
    decorators = [
        dec for dec in test.decorator_list
        if isinstance(dec, ast.Call) and ast.unparse(dec.func) == "pytest.mark.parametrize"
    ]
    if len(decorators) != 1 or len(decorators[0].args) < 2:
        raise AssertionError("Expected a single recorded pytest parametrisation")
    names = ast.literal_eval(decorators[0].args[0])
    values = tuple(tuple(row) for row in ast.literal_eval(decorators[0].args[1]))
    if tuple(names) != EXPECTED_NAMES or values != EXPECTED_ROWS:
        raise AssertionError("Seven recorded numeric comparison cases changed")
    # These source-verified cases use only CaseResult, not Inspect capture logs.
    forbidden = {"FIXTURES", "load_results", "subprocess", "run_task", "eval"}
    names_used = {node.id for node in ast.walk(test) if isinstance(node, ast.Name)}
    if names_used & forbidden:
        raise AssertionError(f"Original case unexpectedly grew fixture/process dependencies: {names_used & forbidden}")
    conf = CONFTEST.read_text(encoding="utf-8")
    conf_tree = ast.parse(conf, filename=CONFTEST.as_posix(), feature_version=(3, 11))
    fixture_sets = [
        ast.literal_eval(node.value) for node in conf_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(x, ast.Name) and x.id == "_SUBPROCESS_FIXTURES" for x in node.targets)
    ]
    if len(fixture_sets) != 1 or "runs" not in fixture_sets[0]:
        raise AssertionError("Original fixture-name collision is no longer present; reassess this lane")
    if "fixturenames" not in conf or "pytest.mark.slow" not in conf:
        raise AssertionError("Collection marker policy changed; re-evaluate the special-case runner")
    print("Source-backed marker audit: seven fixture-independent original parametrised cases", flush=True)
    return len(values)


def main() -> int:
    expected = assert_source_contract()
    node = f"tests/unit/test_compare.py::{TEST_NAME}"
    argv = [
        sys.executable, "-m", "pytest",
        "-o", "addopts=", "-q", "-m", "slow",
        "--color=no", "--maxfail=1", node,
    ]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"Original false-slow regression test failed with exit {result.returncode}")
    if not re.search(rf"\b{expected} passed\b", result.stdout):
        raise RuntimeError("Pytest output did not confirm all seven expected original numeric cases")
    print("Verified seven historical numeric comparison tests without cloud or missing fixtures", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

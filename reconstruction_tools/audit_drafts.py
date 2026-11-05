"""Dependency-free static integrity checks for provisional AEA test transcriptions.

These checks do not prove fidelity to source videos, native pytest correctness,
or behaviour with Inspect AI, LangGraph, and Strands installed.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path
import sys

# Physical source lines in the latest recovered drafts, not Notepad++ editor
# display counts (which can include an extra blank final line).
DRAFTS = {
    "test_judge_FULL_DRAFT.py": 1559,
    "test_readings_FULL_DRAFT.py": 1605,
    "test_export_FULL_DRAFT.py": 748,
    "test_report_FULL_DRAFT.py": 815,
    "test_judge_pairwise_PARTIAL_lines_1_509.py": 509,
    "test_cli_PARTIAL_lines_1_364.py": 364,
    # New screen-recording transcriptions, 5 November 2026. The build-task
    # editor's CRLF character count differs by five; syntax/lines still match.
    "test_build_task_FULL_DRAFT.py": 166,
    "test_run_task_FULL_DRAFT.py": 137,
    "test_scrub_FULL_DRAFT.py": 377,
    "test_cli_pairwise_FULL_DRAFT.py": 200,
    # Source-video reconstructions received 5 November 2026 (second batch).
    "test_judge_double_pairwise_FULL_DRAFT.py": 60,
    "test_judge_double_FULL_DRAFT.py": 70,
    "test_report_pairwise_FULL_DRAFT.py": 91,
    "test_init_FULL_DRAFT.py": 165,
    "test_judge_interrupt_FULL_DRAFT.py": 263,
    "test_stats_compare_FULL_DRAFT.py": 390,
}

# Verify saved-prefix preservation across prior partial transcriptions.
PREFIX_HISTORY = (
    ("test_judge_pairwise_PARTIAL_lines_1_365.py", "test_judge_pairwise_PARTIAL_lines_1_488.py"),
    ("test_judge_pairwise_PARTIAL_lines_1_488.py", "test_judge_pairwise_PARTIAL_lines_1_509.py"),
    ("test_cli_PARTIAL_lines_1_241.py", "test_cli_PARTIAL_lines_1_325.py"),
    ("test_cli_PARTIAL_lines_1_325.py", "test_cli_PARTIAL_lines_1_364.py"),
)

def assigned_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(assigned_names(part) for part in target.elts))
    return set()


def module_bindings(tree: ast.Module) -> set[str]:
    """Find names clearly bound by top-level declarations and assignments."""
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                result.update(assigned_names(target))
        elif isinstance(node, ast.AnnAssign):
            result.update(assigned_names(node.target))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                result.add(alias.asname or alias.name.split(".")[0])
    return result


def resolve_module_path(root: Path, module: str) -> Path | None:
    """Locate either a regular source module or a Python package initialiser."""
    base = root / "src" / Path(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-export-check", action="store_true",
                        help="Check locally copied drafts without production source modules")
    args = parser.parse_args()
    root = args.root.resolve()
    drafts = root / "reconstruction_drafts"
    errors: list[str] = []
    draft_trees: dict[str, ast.Module] = {}
    total_lines = total_tests = 0

    print(f"AEA provisional source audit: {root}")
    for filename, expected_lines in DRAFTS.items():
        path = drafts / filename
        if not path.is_file():
            errors.append(f"Draft missing: {path.relative_to(root)}")
            continue
        source = path.read_text(encoding="utf-8")
        actual_lines = len(source.splitlines())
        if actual_lines != expected_lines:
            errors.append(f"{filename}: expected {expected_lines} physical lines, got {actual_lines}")
        try:
            tree = ast.parse(source, filename=str(path), feature_version=(3, 11))
        except SyntaxError as exc:
            errors.append(f"{filename}: Python 3.11 syntax error: {exc}")
            continue
        draft_trees[filename] = tree
        names = [n.name for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name.startswith("test_")]
        duplicates = {name: count for name, count in Counter(names).items() if count > 1}
        if duplicates:
            errors.append(f"{filename}: duplicate tests: {duplicates}")
        if filename == "test_cli_PARTIAL_lines_1_364.py":
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if not any("CLI_DOUBLES_SOURCE" in assigned_names(t) for t in node.targets):
                    continue
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    try:
                        ast.parse(node.value.value, feature_version=(3, 11))
                    except SyntaxError as exc:
                        errors.append(f"{filename}: CLI_DOUBLES_SOURCE syntax: {exc}")
        total_lines += actual_lines
        total_tests += len(names)
        print(f"  {filename}: {actual_lines} lines, {len(names)} top-level tests, syntax OK")

    for predecessor, successor in PREFIX_HISTORY:
        a, b = drafts / predecessor, drafts / successor
        if not a.is_file() or not b.is_file():
            errors.append(f"Saved prefix checkpoint missing: {predecessor} or {successor}")
        elif not b.read_bytes().startswith(a.read_bytes()):
            errors.append(f"Saved draft prefix mismatch: {predecessor} -> {successor}")
    print(f"Draft totals: {total_lines} lines; {total_tests} top-level tests")

    if not args.skip_export_check:
        missing: set[tuple[str, str]] = set()
        modules: dict[str, set[str]] = {}
        for tree in draft_trees.values():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if node.level or not node.module.startswith("agent_accelerator."):
                    continue
                module = node.module
                module_path = resolve_module_path(root, module)
                if module not in modules:
                    if module_path is None:
                        errors.append(f"Source module unavailable: {module}")
                        modules[module] = set()
                        continue
                    try:
                        module_ast = ast.parse(module_path.read_text(encoding="utf-8"),
                                               feature_version=(3, 11))
                        modules[module] = module_bindings(module_ast)
                    except SyntaxError as exc:
                        errors.append(f"{module}: syntax error: {exc}")
                        modules[module] = set()
                for imported in node.names:
                    if imported.name != "*" and imported.name not in modules[module]:
                        missing.add((module, imported.name))
        for module, name in sorted(missing):
            errors.append(f"Unresolved reconstructed source import: {module}.{name}")

    if errors:
        print("AUDIT FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("DRAFT STATIC CHECKS PASSED; source-video fidelity and native runtime remain unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

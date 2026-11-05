"""Regression tests for the reconstruction-only static audit.

Run without installing AEA dependencies:
    python -m unittest discover -s reconstruction_tools -p 'test_*.py'
"""

import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from reconstruction_tools.audit_drafts import module_bindings, resolve_module_path


class ModuleResolutionTests(unittest.TestCase):
    def test_resolves_regular_python_module(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            path = root / "src" / "agent_accelerator" / "judge.py"
            path.parent.mkdir(parents=True)
            path.write_text("def judge(): pass\n", encoding="utf-8")
            self.assertEqual(resolve_module_path(root, "agent_accelerator.judge"), path)

    def test_resolves_package_initialiser_instead_of_missing_module(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            path = root / "src" / "agent_accelerator" / "adapters" / "__init__.py"
            path.parent.mkdir(parents=True)
            path.write_text("def load_factory(): pass\n", encoding="utf-8")
            self.assertEqual(resolve_module_path(root, "agent_accelerator.adapters"), path)

    def test_unknown_module_is_not_assumed_to_exist(self):
        with TemporaryDirectory() as d:
            self.assertIsNone(resolve_module_path(Path(d), "agent_accelerator.unknown"))

    def test_python_module_preferred_when_both_candidates_exist(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            base = root / "src" / "agent_accelerator"
            (base / "adapters").mkdir(parents=True)
            regular = base / "adapters.py"
            regular.write_text("value = 1\n", encoding="utf-8")
            (base / "adapters" / "__init__.py").write_text("value = 2\n", encoding="utf-8")
            self.assertEqual(resolve_module_path(root, "agent_accelerator.adapters"), regular)


class SourceBindingTests(unittest.TestCase):
    def test_detects_declarations_tuple_assignments_and_alias_imports(self):
        source = (
            "from pathlib import Path as FilePath\n"
            "import json as encoding\n"
            "EXIT_OK, EXIT_ERROR = 0, 2\n"
            "CONFIG: dict = {}\n"
            "class JudgeConfig: pass\n"
            "def check(): pass\n"
            "async def run(): pass\n"
        )
        bindings = module_bindings(ast.parse(source, feature_version=(3, 11)))
        self.assertTrue(
            {"FilePath", "encoding", "EXIT_OK", "EXIT_ERROR",
             "CONFIG", "JudgeConfig", "check", "run"} <= bindings
        )


if __name__ == "__main__":
    unittest.main()

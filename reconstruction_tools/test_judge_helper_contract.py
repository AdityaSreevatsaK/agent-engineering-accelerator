"""Offline contract tests for compatibility aliases in reconstructed judge.py.

These tests extract the *actual* helper functions from source via AST, avoiding
Inspect AI imports, model calls, and unrelated runtime dependencies. Passing
them does NOT establish source-video fidelity or full judge functionality.
"""

import ast
import hashlib
import json
from pathlib import Path
import unittest


JUDGE_SOURCE = Path(__file__).resolve().parents[1] / "src" / "agent_accelerator" / "judge.py"


class FakeToolMessage:
    def __init__(self, function, text):
        self.function = function
        self.text = text


@unittest.skipUnless(JUDGE_SOURCE.is_file(), "Repository's judge.py is unavailable")
class JudgeHelperExportsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(JUDGE_SOURCE.read_text(encoding="utf-8"), feature_version=(3, 11))
        needed = {"_data_marker", "_tool_results_text"}
        exports = {"data_marker", "tool_results_text"}
        selected = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in needed:
                selected.append(node)
            elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in exports for target in node.targets
            ):
                selected.append(node)
        cls.assertEqual(cls, len(selected), 4, "Expected two helper definitions and two aliases")
        module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
        cls.namespace = {
            "hashlib": hashlib,
            "json": json,
            "ChatMessage": object,
            "ChatMessageTool": FakeToolMessage,
            "TOOL_RESULTS_MAX_CHARS": 24,
        }
        exec(compile(module, str(JUDGE_SOURCE), "exec"), cls.namespace)

    def test_public_names_preserve_original_helper_identity(self):
        self.assertIs(self.namespace["data_marker"], self.namespace["_data_marker"])
        self.assertIs(self.namespace["tool_results_text"], self.namespace["_tool_results_text"])

    def test_marker_is_stable_and_tracks_all_input_blocks(self):
        marker = self.namespace["data_marker"]("question", "answer")
        expected = hashlib.sha256(json.dumps(("question", "answer")).encode()).hexdigest()[:16]
        self.assertEqual(marker, expected)
        self.assertNotEqual(marker, self.namespace["data_marker"]("question", "other"))

    def test_tool_text_is_ordered_and_ignores_non_tool_messages(self):
        render = self.namespace["tool_results_text"]
        self.namespace["TOOL_RESULTS_MAX_CHARS"] = 200
        messages = [object(), FakeToolMessage("search", "first"), FakeToolMessage(None, "second")]
        self.assertEqual(render(messages), "[search]\nfirst\n\n[unknown_tool]\nsecond")

    def test_tool_text_truncation_is_explicit(self):
        render = self.namespace["tool_results_text"]
        self.namespace["TOOL_RESULTS_MAX_CHARS"] = 12
        full = "[search]\n" + "x" * 40
        result = render([FakeToolMessage("search", "x" * 40)])
        self.assertTrue(result.startswith(full[:12] + "\n[truncated: "))
        self.assertIn(f"{len(full) - 12} characters omitted]", result)

    def test_no_tool_messages_returns_empty_string(self):
        self.assertEqual(self.namespace["tool_results_text"]([object()]), "")


if __name__ == "__main__":
    unittest.main()

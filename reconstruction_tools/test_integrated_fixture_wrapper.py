"""Pure-stdlib safety and cleanup tests for the temporary Inspect fixture runner."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from reconstruction_tools.run_integrated_offline_safe import (
    CAPTURE,
    EVALUATION_DIR,
    preflight,
    run,
)


class IntegratedFixtureWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = TemporaryDirectory(prefix="aea-safe-synthetic-capture-")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / CAPTURE).parent.mkdir(parents=True)
        self.invocations: list[str] = []

    def fake_runner(self, args: list[str], root: Path) -> int:
        name = args[0]
        self.invocations.append(name)
        if name == "reconstruction_tools.make_synthetic_capture":
            (root / CAPTURE).write_text("CI_SYNTHETIC_CAPTURE_NOT_ORIGINAL", encoding="utf-8")
            (root / EVALUATION_DIR).mkdir()
            (root / EVALUATION_DIR / "synthetic-log.json").write_text("generated", encoding="utf-8")
            return 0
        if name == "reconstruction_tools.run_integrated_offline":
            return self.suite_exit_code
        raise AssertionError(f"Unexpected synthetic runner command: {name}")

    suite_exit_code = 0

    def test_success_deletes_fixture_and_evaluation_directory(self) -> None:
        self.assertEqual(run(root=self.root, runner=self.fake_runner), 0)
        self.assertEqual(
            self.invocations,
            ["reconstruction_tools.make_synthetic_capture", "reconstruction_tools.run_integrated_offline"],
        )
        self.assertFalse((self.root / CAPTURE).exists())
        self.assertFalse((self.root / EVALUATION_DIR).exists())

    def test_test_failure_still_cleans_generated_content(self) -> None:
        self.suite_exit_code = 1
        self.assertEqual(run(root=self.root, runner=self.fake_runner), 1)
        self.assertFalse((self.root / CAPTURE).exists())
        self.assertFalse((self.root / EVALUATION_DIR).exists())

    def test_existing_fixture_is_never_overwritten_or_deleted(self) -> None:
        path = self.root / CAPTURE
        path.write_text("potential ORIGINAL content", encoding="utf-8")
        with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
            run(root=self.root, runner=self.fake_runner)
        self.assertEqual(path.read_text(encoding="utf-8"), "potential ORIGINAL content")
        self.assertEqual(self.invocations, [])

    def test_existing_work_directory_is_never_overwritten_or_deleted(self) -> None:
        path = self.root / EVALUATION_DIR
        path.mkdir()
        (path / "evidence").write_text("original", encoding="utf-8")
        with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
            preflight(self.root)
        self.assertTrue((path / "evidence").is_file())

    def test_modified_fixture_during_suite_is_preserved_for_review(self) -> None:
        def mutate(args: list[str], root: Path) -> int:
            code = self.fake_runner(args, root)
            if args[0] == "reconstruction_tools.run_integrated_offline":
                (root / CAPTURE).write_text("modified", encoding="utf-8")
            return code

        with self.assertRaisesRegex(RuntimeError, "changed during tests"):
            run(root=self.root, runner=mutate)
        self.assertEqual((self.root / CAPTURE).read_text(encoding="utf-8"), "modified")

    def test_failed_generator_returns_error_without_running_suite(self) -> None:
        def fail(args: list[str], root: Path) -> int:
            self.invocations.append(args[0])
            return 3

        self.assertEqual(run(root=self.root, runner=fail), 3)
        self.assertEqual(self.invocations, ["reconstruction_tools.make_synthetic_capture"])
        self.assertFalse((self.root / CAPTURE).exists())


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Checks for the optional local test selector."""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_changed as routing


CHECKS = (
    "tests/selfcheck.py",
    "tests/test_routing.py",
    "scripts/test_check_changed.py",
    "scripts/test_install.py",
)


class ChangedCheckTests(unittest.TestCase):
    def test_narrow_source_selects_its_test(self):
        self.assertEqual(
            routing.select_checks({"tests/routing.py"}, CHECKS),
            ("selected", ("tests/test_routing.py",), ""),
        )

    def test_case_metadata_and_readme_select_the_union_in_makefile_order(self):
        mode, tests, _ = routing.select_checks(
            {"tests/cases/example/checks.json", "README.md"}, CHECKS
        )
        self.assertEqual(mode, "selected")
        self.assertEqual(tests, ("tests/selfcheck.py", "scripts/test_install.py"))

    def test_documentation_only_needs_no_local_test(self):
        self.assertEqual(
            routing.select_checks({"docs/releasing.md"}, CHECKS),
            ("selected", (), ""),
        )

    def test_shared_and_unknown_paths_use_complete_check(self):
        for path in ("baseline/aiscb-core.md", "scripts/install.py", "Makefile",
                     "tests/fixtures/organization-0.1.15/catalog.json",
                     "tests/test_unknown.py;touch unexpected"):
            with self.subTest(path=path):
                mode, tests, reason = routing.select_checks({path}, CHECKS)
                self.assertEqual((mode, tests), ("full", CHECKS))
                self.assertIn(path, reason)

    def test_missing_registered_mapping_uses_complete_check(self):
        mode, _, reason = routing.select_checks({"tests/context_tools.py"}, CHECKS[:2])
        self.assertEqual(mode, "full")
        self.assertIn("absent from CHECK_TESTS", reason)

    def test_any_unknown_path_wins_over_narrow_selection(self):
        mode, _, _ = routing.select_checks({"tests/routing.py", "scripts/install.py"}, CHECKS)
        self.assertEqual(mode, "full")

    def test_changed_paths_include_staged_unstaged_deleted_and_untracked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            for name in ("modified", "deleted"):
                (root / name).write_text("original")
            subprocess.run(["git", "add", "modified", "deleted"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "initial"], cwd=root, check=True)
            (root / "modified").write_text("changed")
            (root / "deleted").unlink()
            (root / "staged").write_text("staged")
            (root / "untracked").write_text("untracked")
            subprocess.run(["git", "add", "staged"], cwd=root, check=True)
            self.assertEqual(routing.changed_paths(root),
                             {"modified", "deleted", "staged", "untracked"})

    def test_dry_run_displays_selection_without_executing(self):
        output = io.StringIO()
        with patch.object(routing, "changed_paths", return_value={"tests/routing.py"}), \
             patch.object(routing, "run_checks") as run, contextlib.redirect_stdout(output):
            self.assertEqual(routing.main(["--dry-run", *CHECKS]), 0)
        run.assert_not_called()
        self.assertIn("Selected checks: tests/test_routing.py", output.getvalue())

    def test_git_failure_runs_full_check(self):
        with patch.object(routing, "changed_paths", side_effect=OSError("missing git")), \
             patch.object(routing.subprocess, "call", return_value=7) as call, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(routing.main(list(CHECKS)), 7)
        call.assert_called_once_with(["make", "check"], cwd=routing.ROOT)

    def test_selected_checks_verify_and_build_before_running(self):
        with patch.object(routing.subprocess, "call", return_value=0) as call, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(routing.run_checks(("tests/test_routing.py",), routing.ROOT), 0)
        commands = [args[0][0] for args in call.call_args_list]
        self.assertEqual(commands, [
            [routing.sys.executable, "scripts/build_baseline.py", "--check"],
            [routing.sys.executable, "scripts/build_baseline.py", "--write"],
            [routing.sys.executable, "tests/test_routing.py"],
        ])


if __name__ == "__main__":
    unittest.main()

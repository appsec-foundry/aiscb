#!/usr/bin/env python3
"""Run the local checks affected by uncommitted changes.

Unknown or shared paths use the complete check. This is a local feedback tool;
the complete check remains the repository and CI gate.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Only sources with a narrow, reviewed relationship to a check belong here.
# Shared installers, policy sources, build code, and configuration use make check.
SOURCE_TESTS = {
    "scripts/check_changed.py": ("scripts/test_check_changed.py",),
    "scripts/spec_guard.py": ("scripts/test_spec_guard.py",),
    "scripts/upgrade_organization.py": ("scripts/test_upgrade_organization.py",),
    "tests/context_comparison.py": ("tests/test_context_comparison.py",),
    "tests/context_fixture.py": ("tests/test_context_comparison.py",),
    "tests/context_tools.py": ("tests/test_context_comparison.py",),
    "tests/cweval_runner.py": ("tests/test_cweval_runner.py",),
    "tests/design_confirmation.py": ("tests/test_design_confirmation.py",),
    "tests/organization.py": ("tests/test_organization.py",),
    "tests/routing.py": ("tests/test_routing.py",),
    "tests/selfcheck.py": ("tests/selfcheck.py", "tests/test_selfcheck.py"),
    "tests/split_routing.py": ("tests/test_split_modules.py",),
    "examples/claude-code-gate/gate.py": ("examples/claude-code-gate/test_gate.py",),
}


def changed_paths(root: Path) -> set[str]:
    """Include staged, unstaged, deleted, and untracked paths."""
    commands = (
        ("git", "diff", "--no-renames", "--name-only", "-z", "HEAD", "--"),
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
    )
    paths = set()
    for command in commands:
        result = subprocess.run(command, cwd=root, capture_output=True, check=True)
        paths.update(os.fsdecode(name) for name in result.stdout.split(b"\0") if name)
    return paths


def select_checks(paths: set[str], tests: tuple[str, ...]) -> tuple[str, tuple[str, ...], str]:
    """Return mode, ordered checks, and the reason for a complete check."""
    if not paths:
        return "none", (), ""

    available = set(tests)
    selected = set()
    for path in sorted(paths):
        if path in SOURCE_TESTS:
            needed = SOURCE_TESTS[path]
        elif path == "README.md":
            needed = ("tests/selfcheck.py", "scripts/test_install.py")
        elif path.startswith("tests/cases/"):
            needed = ("tests/selfcheck.py",)
        elif path in {"CHANGELOG.md", "tests/README.md"} or (
            path.startswith("docs/") and path.endswith(".md")
        ):
            needed = ()
        elif path in available:
            needed = (path,)
        else:
            return "full", tests, f"no narrow mapping for {path}"

        if any(test not in available for test in needed):
            return "full", tests, f"mapped check for {path} is absent from CHECK_TESTS"
        selected.update(needed)

    return "selected", tuple(test for test in tests if test in selected), ""


def run_checks(tests: tuple[str, ...], root: Path) -> int:
    # Keep the source and generated development artifact in sync, as make check does.
    for flag in ("--check", "--write"):
        code = subprocess.call([sys.executable, "scripts/build_baseline.py", flag], cwd=root)
        if code:
            return code
    for test in tests:
        print(f"python3 {test}", flush=True)
        code = subprocess.call([sys.executable, test], cwd=root)
        if code:
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show the selection without running checks")
    parser.add_argument("tests", nargs="+", help="the Makefile's CHECK_TESTS list")
    args = parser.parse_args(argv)
    tests = tuple(args.tests)
    if len(tests) != len(set(tests)) or any(not (ROOT / test).is_file() for test in tests):
        parser.error("CHECK_TESTS contains a duplicate or missing file")

    try:
        paths = changed_paths(ROOT)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Cannot determine changes ({exc}); running make check", flush=True)
        return 0 if args.dry_run else subprocess.call(["make", "check"], cwd=ROOT)

    mode, selected, reason = select_checks(paths, tests)
    print("Changed paths: " + (", ".join(sorted(paths)) if paths else "none"), flush=True)
    if mode == "none":
        print("No uncommitted changes; no local checks selected.", flush=True)
        return 0
    if mode == "full":
        print(f"Full check: {reason}", flush=True)
        return 0 if args.dry_run else subprocess.call(["make", "check"], cwd=ROOT)
    print("Selected checks: " + (", ".join(selected) if selected else "none (documentation only)"),
          flush=True)
    return 0 if args.dry_run or not selected else run_checks(selected, ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

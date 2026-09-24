#!/usr/bin/env python3
"""Measure statement coverage for the free `make check` suite.

Two things about this repository make a plain `coverage run` misleading, and
both are handled here.

The suite is a set of standalone scripts rather than a pytest run, so each one
is measured separately and the results are combined afterwards.

Several of those scripts exercise the code under test in a subprocess:
scripts/test_spec_guard.py runs scripts/spec_guard.py through
`subprocess.run`, and scripts/test_install.py does the same for parts of
scripts/install.py. Without the sitecustomize hook installed below, coverage
sees nothing of those child processes and reports spec_guard.py as 0% covered
although its tests reach 91% of it.

Usage: coverage_report.py [--xml PATH] TEST_SCRIPT [TEST_SCRIPT ...]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Test files measure the code under test, not themselves, and neither does this
# script. tests/run.py is the model runner: it only executes during `make test`,
# which spends tokens and hours, so its coverage under the free suite would say
# nothing useful. The probe_* scripts are opt-in checks against installed CLIs
# and never run in the free suite either.
OMIT = ("*/test_*.py", "*/tests/run.py", "*/scripts/probe_*.py",
        "*/scripts/coverage_report.py")

SITECUSTOMIZE = "import coverage\ncoverage.process_startup()\n"


def write_config(workdir: Path) -> Path:
    (workdir / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    rcfile = workdir / "coveragerc"
    rcfile.write_text(
        "[run]\n"
        # Absolute, so children started in another directory still match.
        f"source = {REPO / 'scripts'},{REPO / 'tests'},{REPO / 'examples'}\n"
        "parallel = True\n"
        f"data_file = {workdir / 'data'}\n"
        "omit =\n" + "".join(f"    {pattern}\n" for pattern in OMIT),
        encoding="utf-8",
    )
    return rcfile


def child_env(workdir: Path, rcfile: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["COVERAGE_PROCESS_START"] = str(rcfile)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(workdir), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])]
    )
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tests", nargs="+", help="test scripts to measure")
    parser.add_argument("--xml", type=Path,
                        help="also write a Cobertura report here, for CI upload")
    args = parser.parse_args(argv)

    try:
        import coverage  # noqa: F401
    except ImportError:
        print("coverage is not installed: python3 -m pip install coverage",
              file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        rcfile = write_config(workdir)
        env = child_env(workdir, rcfile)

        failed = []
        for test in args.tests:
            # `python3 test.py` puts the test's directory first on sys.path;
            # `coverage run` does not, so sibling imports would fail unmeasured.
            test_env = dict(env)
            test_env["PYTHONPATH"] = os.pathsep.join(
                [str((REPO / test).parent), env["PYTHONPATH"]])
            result = subprocess.run(
                [sys.executable, "-m", "coverage", "run",
                 f"--rcfile={rcfile}", test],
                cwd=REPO, env=test_env,
            )
            if result.returncode != 0:
                failed.append(test)

        subprocess.run([sys.executable, "-m", "coverage", "combine",
                        f"--rcfile={rcfile}"],
                       cwd=REPO, env=env, stdout=subprocess.DEVNULL)
        report = subprocess.run([sys.executable, "-m", "coverage", "report",
                                 f"--rcfile={rcfile}", "--skip-empty"],
                                cwd=REPO, env=env)
        if args.xml is not None:
            subprocess.run([sys.executable, "-m", "coverage", "xml",
                            f"--rcfile={rcfile}", "-o", str(args.xml.resolve())],
                           cwd=REPO, env=env, stdout=subprocess.DEVNULL)

    if failed:
        print(f"\ntests failed, coverage is incomplete: {', '.join(failed)}",
              file=sys.stderr)
        return 1
    return report.returncode


if __name__ == "__main__":
    raise SystemExit(main())

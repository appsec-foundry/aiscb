#!/usr/bin/env python3
"""Keep the session-start version hook honest.

The hook runs in every agent session that installs it, reads a file the
installer placed, and prints the result into the session.

The helper finds the baseline relative to its own location, so the cases below
move that location to a prepared directory instead of copying the helper: a
copy would be a different file, and the coverage of the shipped one would stay
at zero. One case runs the real script as a subprocess, which is how an agent
invokes it.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HELPER = REPO / "scripts" / "show_baseline_version.py"
BASELINE = "secure-coding-baseline.md"
MAX_BASELINE_BYTES = 256 * 1024
REGISTRY_FILE = ".config/aiscb/installations.json"

sys.path.insert(0, str(HELPER.parent))
import show_baseline_version as hook  # noqa: E402

VALID_ID = "aiscb-0.1.12"
VALID = f"# AI Secure Coding Baseline\n\n`baseline-id: {VALID_ID}`\n\nRules follow.\n"

# The installer may place the baseline beside the helper or one level above it.
BESIDE = {"scripts/" + BASELINE: VALID}
ABOVE = {BASELINE: VALID}

READ_FAILURES = [
    ("no baseline anywhere", {}),
    ("empty baseline", {BASELINE: ""}),
    ("no baseline ID", {BASELINE: "# Heading\n\nNo identifier here.\n"}),
    ("two baseline IDs",
     {BASELINE: f"`baseline-id: {VALID_ID}`\n\n`baseline-id: aiscb-0.2.0`\n"}),
    ("ID not at line start", {BASELINE: f"see `baseline-id: {VALID_ID}`\n"}),
    ("malformed version", {BASELINE: "`baseline-id: aiscb-1.2`\n"}),
    ("leading zero in the version", {BASELINE: "`baseline-id: aiscb-0.01.0`\n"}),
    ("invalid UTF-8", {BASELINE: b"`baseline-id: aiscb-0.1.12`\n\xff\xfe\n"}),
    ("one byte over the size limit",
     {BASELINE: VALID + "x" * (MAX_BASELINE_BYTES - len(VALID) + 1)}),
    ("a symlinked baseline", {BASELINE: ("symlink", "elsewhere.md"),
                              "elsewhere.md": VALID}),
    ("a directory where the baseline belongs", {BASELINE + "/keep": ""}),
]


def build(layout: dict[str, object]) -> Path:
    """Lay out the given files in a fresh directory that the helper will search."""
    root = Path(tempfile.mkdtemp()).resolve()
    (root / "scripts").mkdir()
    for name, content in layout.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, tuple):
            target.symlink_to(root / content[1])
        elif isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    return root


@contextlib.contextmanager
def helper_in(root: Path):
    """Pretend the helper was installed into the prepared directory."""
    original = hook.__file__
    hook.__file__ = str(root / "scripts" / HELPER.name)
    try:
        yield
    finally:
        hook.__file__ = original


@contextlib.contextmanager
def home_at(root: Path):
    """Point the registry lookup at the prepared directory, not the real home."""
    previous = {name: os.environ.get(name) for name in ("HOME", "USERPROFILE")}
    os.environ.update({name: str(root) for name in previous})
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def call(layout: dict[str, object],
         argv: list[str] | None = None) -> tuple[object, str, str]:
    return call_in(build(layout), argv)


def call_in(root: Path, argv: list[str] | None = None) -> tuple[object, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with helper_in(root), home_at(root), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        try:
            code: object = hook.main(argv or [])
        except SystemExit as exc:  # argparse rejects unknown arguments this way
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def check_success(failures: list[str]) -> None:
    """A readable baseline yields the ID, in both output formats."""
    for label, layout in (("beside the helper", BESIDE), ("one level above", ABOVE)):
        code, out, err = call(layout)
        if code != 0:
            failures.append(f"{label}: returned {code}: {err[:200]}")
        elif VALID_ID not in out:
            failures.append(f"{label}: banner lacks the ID: {out[:200]!r}")

    code, out, err = call(ABOVE, ["--output", "json"])
    if code != 0:
        failures.append(f"json output: returned {code}: {err[:200]}")
    else:
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as exc:
            failures.append(f"json output is not JSON: {exc}")
        else:
            if VALID_ID not in payload.get("systemMessage", ""):
                failures.append(f"json output lacks the ID: {payload}")

    # The helper reads up to the limit, so the limit itself must still work.
    at_limit = VALID + "x" * (MAX_BASELINE_BYTES - len(VALID))
    code, out, _ = call({BASELINE: at_limit})
    if code != 0 or VALID_ID not in out:
        failures.append(
            f"baseline at the size limit: returned {code}, stdout {out[:120]!r}"
        )

    # A baseline beside the helper wins over one above it, and nothing further
    # up the tree is searched, so an unrelated baseline cannot be picked up.
    code, out, _ = call({**ABOVE,
                         "scripts/" + BASELINE: VALID.replace(VALID_ID, "aiscb-9.9.9")})
    if "aiscb-9.9.9" not in out:
        failures.append(f"baseline beside the helper must win: {out[:120]!r}")


def check_failures(failures: list[str]) -> None:
    """Every unreadable baseline fails closed, without leaking internals."""
    for label, layout in READ_FAILURES:
        code, out, err = call(layout)
        if code != 1:
            failures.append(f"{label}: expected 1, got {code} / stdout {out[:120]!r}")
        if out.strip():
            failures.append(f"{label}: wrote a banner anyway: {out[:120]!r}")
        if "Traceback" in err or ".py" in err:
            failures.append(f"{label}: leaked internals: {err[:200]!r}")


def registry_layout(section: object) -> dict[str, object]:
    """The installer's registry, as the helper finds it below the home directory."""
    return {
        **ABOVE,
        REGISTRY_FILE: json.dumps(
            {"schema": 1, "projects": {}, "user": None, "update_check": section}
        ),
    }


def check_update_note(failures: list[str]) -> None:
    """Only a genuinely newer release of this baseline is announced."""
    silent = [
        ("the same version", {"latest": VALID_ID}),
        ("an older release", {"latest": "aiscb-0.1.9"}),
        ("another baseline's name", {"latest": "acme-9.9.9"}),
        ("a value that is not a version", {"latest": "; rm -rf /"}),
        ("a missing version", {"enabled": False}),
        ("a section that is not an object", "aiscb-9.9.9"),
    ]
    for label, section in silent:
        code, out, _ = call(registry_layout(section))
        if code != 0 or "Update" in out:
            failures.append(f"{label}: expected no note, got {out[:160]!r}")

    code, out, _ = call(registry_layout({"latest": "aiscb-0.2.0"}))
    if code != 0 or "Update 0.2.0" not in out:
        failures.append(f"a newer release must be announced: {out[:160]!r}")
    if "https://github.com/appsec-foundry/aiscb#quick-start" not in out:
        failures.append(f"without an installer the note names the Quick start: {out[:160]!r}")
    if "python3" in out or "curl" in out:
        failures.append(f"no installer means no command: {out[:160]!r}")

    root = build({**registry_layout({"latest": "aiscb-0.2.0"}),
                  "scripts/install.py": "raise SystemExit(0)\n"})
    _code, out, _err = call_in(root)
    expected = f"python3 {root / 'scripts' / 'install.py'} --update"
    if expected not in out:
        failures.append(f"the note must name the signed update command: {out[:200]!r}")
    if "quick-start" in out or "curl" in out:
        failures.append(f"with an installer the note names only its command: {out[:200]!r}")
    if (root / "scripts" / "updated").exists():
        failures.append("the hook must never run the update itself")

    for label, payload in (
        ("invalid registry JSON", "not json"),
        ("a registry without the section", json.dumps({"schema": 1})),
        ("an oversized registry", json.dumps({"schema": 1, "pad": "x" * 200_000})),
    ):
        code, out, _ = call({**ABOVE, REGISTRY_FILE: payload})
        if code != 0 or "Update" in out:
            failures.append(
                f"{label}: expected a plain banner, got {code} {out[:160]!r}"
            )


def check_background_refresh(failures: list[str]) -> None:
    """The refresh runs only when it was allowed and the cache is stale."""
    marker_installer = (
        "import pathlib, sys\n"
        "pathlib.Path(__file__).with_name('refreshed')"
        ".write_text(' '.join(sys.argv[1:]))\n"
    )
    stale, fresh = 1, int(time.time())
    cases = [
        ("allowed and stale", {"enabled": True, "checked": stale}, True),
        ("allowed but fresh", {"enabled": True, "checked": fresh}, False),
        ("not allowed", {"enabled": False, "checked": stale}, False),
        ("never asked", {"checked": stale}, False),
    ]
    for label, section, expected in cases:
        root = build({**registry_layout(section),
                      "scripts/install.py": marker_installer})
        marker = root / "scripts" / "refreshed"
        call_in(root)
        for _ in range(50):
            if marker.is_file():
                break
            time.sleep(0.1)
        if marker.is_file() != expected:
            failures.append(
                f"{label}: refresh {'missing' if expected else 'started anyway'}"
            )
        elif expected and "--refresh-update-cache" not in marker.read_text():
            failures.append(f"{label}: refreshed with {marker.read_text()[:80]!r}")


def check_arguments(failures: list[str]) -> None:
    """An unknown output format is rejected rather than guessed."""
    code, out, _ = call(ABOVE, ["--output", "yaml"])
    if code != 2:
        failures.append(f"unknown format: expected 2, got {code}")
    if VALID_ID in out:
        failures.append("unknown format still printed the ID")


def check_installed_script(failures: list[str]) -> None:
    """The way an agent runs it: the real script, as its own process."""
    for argv, check in (([], lambda text: VALID_ID in text),
                        (["--output", "json"],
                         lambda text: VALID_ID in json.loads(text)["systemMessage"])):
        proc = subprocess.run([sys.executable, str(HELPER), *argv],
                              capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            failures.append(
                f"installed script {argv}: exited {proc.returncode}: {proc.stderr[:200]}"
            )
            continue
        try:
            if not check(proc.stdout):
                failures.append(f"installed script {argv}: {proc.stdout[:200]!r}")
        except (json.JSONDecodeError, KeyError) as exc:
            failures.append(f"installed script {argv}: unusable output: {exc}")


def main() -> int:
    failures: list[str] = []
    check_success(failures)
    check_failures(failures)
    check_update_note(failures)
    check_background_refresh(failures)
    check_arguments(failures)
    check_installed_script(failures)

    for line in failures:
        print(f"FAIL: {line}")
    if failures:
        return 1
    print(f"version hook: ok ({len(READ_FAILURES)} read failures rejected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

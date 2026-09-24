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
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
HELPER = REPO / "scripts" / "show_baseline_version.py"
BASELINE = "secure-coding-baseline.md"
MAX_BASELINE_BYTES = 256 * 1024
REGISTRY_FILE = ".config/aiscb/installations.json"

sys.path.insert(0, str(HELPER.parent))
import show_baseline_version as hook  # noqa: E402

VALID_ID = "aiscb-0.1.19"
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
    ("invalid UTF-8", {BASELINE: b"`baseline-id: aiscb-0.1.19`\n\xff\xfe\n"}),
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

    code, out, err = call(ABOVE, ["--output", "copilot"])
    if code != 0:
        failures.append(f"copilot output: returned {code}: {err[:200]}")
    else:
        lines = out.splitlines()
        try:
            progress, result = (json.loads(line) for line in lines)
        except (ValueError, json.JSONDecodeError) as exc:
            failures.append(f"copilot output is not line-delimited JSON: {exc}")
        else:
            if (
                progress.get("type") != "progress"
                or progress.get("temporary") is not False
                or VALID_ID not in progress.get("message", "")
                or result != {}
            ):
                failures.append(f"copilot output has the wrong shape: {lines}")

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
    """The banner distinguishes current, newer, and unchecked releases."""
    checked = 1_789_027_200
    checked_on = time.strftime("%Y-%m-%d", time.gmtime(checked))
    current = [
        ("the same version", {"latest": VALID_ID, "checked": checked}),
        ("an older release", {"latest": "aiscb-0.1.9", "checked": checked}),
    ]
    for label, section in current:
        code, out, _ = call(registry_layout(section))
        if code != 0 or f"no newer release known at last check (checked {checked_on})" not in out:
            failures.append(f"{label}: expected current status, got {out[:160]!r}")

    unchecked = [
        ("a version without a check time", {"latest": VALID_ID}),
        ("another baseline's name", {"latest": "acme-9.9.9"}),
        ("a value that is not a version", {"latest": "; rm -rf /"}),
        ("a missing version", {"enabled": False}),
        ("a section that is not an object", "aiscb-9.9.9"),
    ]
    for label, section in unchecked:
        code, out, _ = call(registry_layout(section))
        if code != 0 or "update status not checked" not in out:
            failures.append(f"{label}: expected unchecked status, got {out[:160]!r}")

    code, out, _ = call(registry_layout(
        {"latest": "aiscb-0.2.0", "checked": checked}
    ))
    if code != 0 or f"update 0.2.0 available (checked {checked_on})" not in out:
        failures.append(f"a newer release must be announced: {out[:160]!r}")
    if "https://github.com/appsec-foundry/aiscb#update" not in out:
        failures.append(f"the note must link the update guide: {out[:160]!r}")
    if "python3" in out or "curl" in out:
        failures.append(f"no installer means no command: {out[:160]!r}")

    root = build({**registry_layout({"latest": "aiscb-0.2.0", "checked": checked}),
                  "scripts/install.py": "raise SystemExit(0)\n"})
    _code, out, _err = call_in(root)
    if "https://github.com/appsec-foundry/aiscb#update" not in out:
        failures.append(f"the note must link the update guide: {out[:200]!r}")
    if "python3" in out or "curl" in out or "--update" in out:
        failures.append(
            f"the note is a pointer into an agent session, never a command: {out[:200]!r}"
        )

    for label, payload in (
        ("invalid registry JSON", "not json"),
        ("a registry without the section", json.dumps({"schema": 1})),
        ("an oversized registry", json.dumps({"schema": 1, "pad": "x" * 200_000})),
    ):
        code, out, _ = call({**ABOVE, REGISTRY_FILE: payload})
        if code != 0 or "update status not checked" not in out:
            failures.append(f"{label}: expected unchecked status, got {code} {out[:160]!r}")


def check_cache_age(failures: list[str]) -> None:
    """A pending or unsuccessful refresh must not make old knowledge current."""
    checked = 1_789_027_200
    for latest in (VALID_ID, "aiscb-0.1.9", "aiscb-0.2.0"):
        for age in (86_399, 86_400, 86_401, 864_000):
            for enabled in (False, True):
                root = build({
                    **registry_layout({"latest": latest, "checked": checked,
                                       "enabled": enabled}),
                    "scripts/install.py": "raise SystemExit(1)\n",
                })
                state = root / REGISTRY_FILE
                original = state.read_bytes()
                with patch("time.time", return_value=checked + age), \
                        patch.object(hook.subprocess, "Popen") as refresh:
                    # No cache write: a pending or failed check has no new evidence.
                    notes = [hook.update_note(VALID_ID, root / "scripts", root)
                             for _ in range(2)]
                stale = age >= 86_400
                for note in notes:
                    if ("check stale" in note) != stale or "up to date" in note:
                        failures.append(f"cache age {age}: misleading status: {note}")
                    if latest == "aiscb-0.2.0":
                        if "update 0.2.0 available" not in note or hook.UPDATE_GUIDE not in note:
                            failures.append(f"cache age {age}: update notice lost: {note}")
                    elif "no newer release known at last check" not in note:
                        failures.append(f"cache age {age}: missing qualification: {note}")
                if refresh.called != (enabled and stale):
                    failures.append(f"cache age {age}: refresh permission or interval changed")
                if state.read_bytes() != original:
                    failures.append("reporting cache age changed the stored check")


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
    import build_baseline
    with tempfile.TemporaryDirectory(prefix="aiscb-hook-installed-") as tmp:
        root = Path(tmp)
        installed = root / HELPER.name
        installed.write_bytes(HELPER.read_bytes())
        (root / BASELINE).write_bytes(build_baseline.validate()[2])
        check_script_at(installed, failures)


def check_script_at(installed: Path, failures: list[str]) -> None:
    for argv, check in (([], lambda text: VALID_ID in text),
                        (["--output", "json"],
                         lambda text: VALID_ID in json.loads(text)["systemMessage"])):
        proc = subprocess.run([sys.executable, str(installed), *argv],
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


def check_update_provider(failures):
    """A cached old/disabled/foreign plugin must never advertise the skill."""
    for folder in ("marketplace-one/revision-a", "another-catalog/revision-b"):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            project = home / "workspace"
            project.mkdir()
            config = home / ".claude"
            root = config / "plugins/cache" / folder
            files = {
                home / ".aiscb/installation.json": {},
                config / "settings.json": {"enabledPlugins": {"appsec-advisor@example": True}},
                config / "plugins/installed_plugins.json": {"version": 2, "plugins": {
                    "appsec-advisor@example": [{"scope": "user", "installPath": str(root)}]}},
                root / ".claude-plugin/plugin.json": {"name": "appsec-advisor"},
                root / "data/aiscb-update-provider.json": {
                    "schema": 1, "skill": "/appsec-advisor:update-baseline",
                    "installer_protocol": "aiscb-refresh-installed-v1"},
            }
            for path, value in files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            skill = root / "skills/update-baseline/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("Update skill")
            with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}):
                if hook.update_guide(home, project, claude=True) != "/appsec-advisor:update-baseline":
                    failures.append("compatible enabled provider was not offered")
                if hook.update_guide(home, project) != hook.UPDATE_GUIDE:
                    failures.append("Claude skill leaked into another client")
                for path, invalid in (
                    (root / "data/aiscb-update-provider.json", {}),
                    (root / "data/aiscb-update-provider.json", {**files[root / "data/aiscb-update-provider.json"],
                                                             "skill": "$(touch /tmp/never)"}),
                    (root / ".claude-plugin/plugin.json", {"name": "another-plugin"}),
                    (config / "settings.json", {"enabledPlugins": {"appsec-advisor@example": False}}),
                    (config / "plugins/installed_plugins.json", {"version": 2, "plugins": []}),
                ):
                    original = path.read_bytes()
                    path.write_text(json.dumps(invalid))
                    if hook.update_guide(home, project, claude=True) != hook.UPDATE_GUIDE:
                        failures.append(f"invalid provider accepted: {path.name}")
                    path.write_bytes(original)
                local = project / ".claude/settings.local.json"
                local.parent.mkdir()
                local.write_text(json.dumps({"enabledPlugins": {"appsec-advisor@example": False}}))
                if hook.update_guide(home, project, claude=True) != hook.UPDATE_GUIDE:
                    failures.append("project disable ignored")


def session_call(root: Path, part: int, disable: str | None) -> dict:
    environment = {} if disable is None else {"AISCB_DISABLE": disable}
    with helper_in(root), patch.dict(os.environ, environment):
        if disable is None:
            os.environ.pop("AISCB_DISABLE", None)
        return hook.session_context(part)


def check_session_context(failures: list[str]) -> None:
    """The switchable loader supplies the rules in parts or stops the session."""
    root = build(ABOVE)
    result = session_call(root, 0, "maybe")
    if result.get("continue") is not False or "0 or 1" not in result.get("stopReason", ""):
        failures.append(f"an invalid AISCB_DISABLE value did not stop: {result}")

    first = session_call(root, 0, None)
    context = first.get("hookSpecificOutput", {}).get("additionalContext", "")
    if (not context.startswith(f"aiscb-session-part: 1/{hook.SESSION_PARTS}; source: ")
            or "Rules follow." not in context
            or VALID_ID not in first.get("systemMessage", "")):
        failures.append(f"part 1 does not carry the rules and the ID: {first}")
    second = session_call(root, 1, "0")
    if "systemMessage" in second or "Rules follow." in json.dumps(second):
        failures.append(f"a later part repeated the banner or the first part: {second}")

    disabled = session_call(root, 0, "1")
    context = disabled.get("hookSpecificOutput", {}).get("additionalContext", "")
    if (not context.startswith("aiscb-session-disabled: ") or "Rules follow." in context
            or "AISCB_DISABLE=1" not in disabled.get("systemMessage", "")):
        failures.append(f"the opt-out still supplied rules: {disabled}")

    for label, layout in (
        ("a missing baseline", {}),
        ("a baseline beyond the session capacity",
         {BASELINE: VALID + "x" * (hook.SESSION_PARTS * hook.SESSION_PART_CHARS)}),
    ):
        stopped = session_call(build(layout), 0, "1")
        if stopped.get("continue") is not False or "hookSpecificOutput" in stopped:
            failures.append(f"{label} did not stop the session: {stopped}")


def check_session_arguments(failures: list[str]) -> None:
    """The hook modes refuse ambiguous arguments and report a broken install."""
    for argv in (["--session-check", "--part", "0"], ["--session-context"],
                 ["--part", "1"]):
        code, out, _ = call(ABOVE, argv)
        if code != 2 or out:
            failures.append(f"{argv} was accepted: code={code} out={out!r}")

    code, out, _ = call(ABOVE, ["--session-check"])
    if code != 0 or out.strip() != "{}":
        failures.append(f"a valid installation blocked the prompt: {out!r}")
    code, out, _ = call({}, ["--session-check"])
    try:
        decision = json.loads(out)
    except json.JSONDecodeError:
        decision = {}
    if code != 0 or decision.get("decision") != "block" or decision.get("continue") is not False:
        failures.append(f"a missing baseline did not block the prompt: {out!r}")

    code, out, _ = call(ABOVE, ["--session-context", "--part", "0"])
    try:
        result = json.loads(out)
    except json.JSONDecodeError:
        result = {}
    if (code != 0 or VALID_ID not in result.get("systemMessage", "")
            or "update status not checked" not in result.get("systemMessage", "")):
        failures.append(f"part 0 lacks the banner and update note: {out!r}")

    code, out, err = call({}, [])
    if code != 1 or out or "Could not read" not in err:
        failures.append(f"a missing baseline was not reported: {code} {out!r} {err!r}")
    code, out, _ = call(ABOVE, ["--output", "copilot"])
    lines = out.splitlines()
    try:
        progress = json.loads(lines[0])
    except (IndexError, json.JSONDecodeError):
        progress = {}
    if (code != 0 or len(lines) != 2 or lines[1] != "{}"
            or progress.get("type") != "progress" or VALID_ID not in progress.get("message", "")):
        failures.append(f"Copilot output is malformed: {out!r}")


def check_provider_refusals(failures: list[str]) -> None:
    """Ambiguous, oversized or misplaced provider metadata keeps the URL."""
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        project = home / "workspace"
        project.mkdir()
        config = home / ".claude"
        cache = config / "plugins/cache"
        root = cache / "catalog/revision"
        outside = home / "outside"
        name = "appsec-advisor@example"
        (root / "skills/update-baseline").mkdir(parents=True)
        (root / "skills/update-baseline/SKILL.md").write_text("Update skill")
        outside.mkdir()

        def write(path: Path, value: object) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))

        def entry(scope: str, path: Path = root, **extra: object) -> dict:
            return {"scope": scope, "installPath": str(path), **extra}

        write(config / "settings.json", {"enabledPlugins": {name: True}})
        write(root / ".claude-plugin/plugin.json", {"name": "appsec-advisor"})
        write(root / "data/aiscb-update-provider.json", {
            "schema": 1, "skill": "/appsec-advisor:update-baseline",
            "installer_protocol": "aiscb-refresh-installed-v1"})
        installed = config / "plugins/installed_plugins.json"

        def guide(plugins: object) -> str:
            write(installed, plugins)
            with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}):
                return hook.update_guide(home, project, claude=True)

        skill = "/appsec-advisor:update-baseline"
        local = entry("local", projectPath=str(project))
        if guide({"version": 2, "plugins": {name: [entry("user", outside), local]}}) != skill:
            failures.append("a project-local provider did not take precedence")
        if guide({"version": 2, "plugins": {name: [
                entry("project", projectPath=str(home / "elsewhere"))]}}) != hook.UPDATE_GUIDE:
            failures.append("a provider installed for another project was offered")
        for label, plugins in (
            ("two providers of equal rank", {"version": 2, "plugins": {name: [
                entry("user"), entry("user", outside)]}}),
            ("a provider outside the plugin cache", {"version": 2, "plugins": {
                name: [entry("user", outside)]}}),
            ("an entry list that is not a list", {"version": 2, "plugins": {name: {}}}),
            ("an oversized entry list", {"version": 2, "plugins": {name: [entry("user")] * 65}}),
            ("an entry that is not an object", {"version": 2, "plugins": {name: ["user"]}}),
            ("an unknown registry version", {"version": 3, "plugins": {name: [entry("user")]}}),
            ("an install path that does not exist", {"version": 2, "plugins": {
                name: [entry("user", root / "missing")]}}),
            ("registry metadata that is not an object", []),
        ):
            if guide(plugins) != hook.UPDATE_GUIDE:
                failures.append(f"{label} was offered as the update skill")

        good = {"version": 2, "plugins": {name: [entry("user")]}}
        (root / "skills/update-baseline/SKILL.md").unlink()
        if guide(good) != hook.UPDATE_GUIDE:
            failures.append("a provider without its update skill was offered")
        (root / "skills/update-baseline/SKILL.md").write_text("Update skill")

        write(config / "settings.json", {"enabledPlugins": [name]})
        if guide(good) != hook.UPDATE_GUIDE:
            failures.append("malformed enabledPlugins was trusted")
        (config / "settings.json").write_text("x" * (hook.MAX_REGISTRY_BYTES + 1))
        if guide(good) != hook.UPDATE_GUIDE:
            failures.append("oversized settings were read")
        (config / "settings.json").unlink()
        (config / "settings.json").symlink_to(outside / "settings.json")
        write(outside / "settings.json", {"enabledPlugins": {name: True}})
        if guide(good) != hook.UPDATE_GUIDE:
            failures.append("symlinked settings were followed")


def main() -> int:
    failures: list[str] = []
    check_session_context(failures)
    check_session_arguments(failures)
    check_provider_refusals(failures)
    check_success(failures)
    check_failures(failures)
    check_update_note(failures)
    check_cache_age(failures)
    check_background_refresh(failures)
    check_arguments(failures)
    check_installed_script(failures)
    check_update_provider(failures)

    for line in failures:
        print(f"FAIL: {line}")
    if failures:
        return 1
    print(f"version hook: ok ({len(READ_FAILURES)} read failures rejected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Print the installed baseline ID for agent session-start hooks."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BASELINE = "secure-coding-baseline.md"
INSTALLER = "install.py"
UPDATE_GUIDE = "https://github.com/appsec-foundry/aiscb#update"
REGISTRY = Path(".config") / "aiscb" / "installations.json"
USER_DATA = Path(".local") / "share" / "aiscb"
MAX_BASELINE_BYTES = 256 * 1024
MAX_REGISTRY_BYTES = 128 * 1024
CHECK_INTERVAL = 24 * 60 * 60
SESSION_PARTS = 4
SESSION_PART_CHARS = 7100
SEMVER_TEXT = (
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
BASELINE_ID_RE = re.compile(
    rf"^`baseline-id:\s*(?P<id>[a-z][a-z0-9-]*-{SEMVER_TEXT})`",
    re.MULTILINE,
)
RELEASE_RE = re.compile(rf"(?P<name>[a-z][a-z0-9-]*)-(?P<version>{SEMVER_TEXT})")


def read_provider_json(path: Path) -> dict:
    """Read bounded display metadata; never execute plugin or workspace content."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("provider metadata is not a regular file")
    with path.open("rb") as handle:
        raw = handle.read(MAX_REGISTRY_BYTES + 1)
    if len(raw) > MAX_REGISTRY_BYTES:
        raise ValueError("provider metadata too large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid provider metadata")
    return value


def update_guide(home: Path, cwd: Path, *, claude: bool = False) -> str:
    """Prefer a compatible enabled Claude plugin; ambiguous state keeps the URL.

    This is display-only discovery, never authorization to update. Development
    --plugin-dir sessions without an installation record retain the URL.
    """
    if not claude:
        return UPDATE_GUIDE
    try:
        config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude")
        enabled = {}
        for path in (config / "settings.json", cwd / ".claude/settings.json",
                     cwd / ".claude/settings.local.json"):
            if path.exists():
                values = read_provider_json(path).get("enabledPlugins", {})
                if not isinstance(values, dict):
                    return UPDATE_GUIDE
                enabled.update(values)
        plugins = read_provider_json(config / "plugins/installed_plugins.json")
        if plugins.get("version") != 2 or not isinstance(plugins.get("plugins"), dict):
            return UPDATE_GUIDE
        choices = []
        for name, entries in plugins["plugins"].items():
            if not name.startswith("appsec-advisor@") or enabled.get(name) is not True:
                continue
            if not isinstance(entries, list) or len(entries) > 64:
                return UPDATE_GUIDE
            for item in entries:
                if not isinstance(item, dict):
                    return UPDATE_GUIDE
                scope = item.get("scope")
                if scope == "user":
                    priority = 0
                elif scope in {"project", "local"} and item.get("projectPath") == str(cwd):
                    priority = 2 if scope == "local" else 1
                else:
                    continue
                choices.append((priority, item.get("installPath")))
        if not choices:
            return UPDATE_GUIDE
        selected = [path for rank, path in choices if rank == max(c[0] for c in choices)]
        if len(selected) != 1 or not isinstance(selected[0], str):
            return UPDATE_GUIDE
        root = Path(selected[0]).resolve(strict=True)
        if not root.is_relative_to((config / "plugins/cache").resolve(strict=True)):
            return UPDATE_GUIDE
        capability = read_provider_json(root / "data/aiscb-update-provider.json")
        if type(capability.get("schema")) is not int or capability != {"schema": 1, "skill": "/appsec-advisor:update-baseline",
                          "installer_protocol": "aiscb-refresh-installed-v1"}:
            return UPDATE_GUIDE
        if read_provider_json(root / ".claude-plugin/plugin.json").get("name") != "appsec-advisor":
            return UPDATE_GUIDE
        if not (root / "skills/update-baseline/SKILL.md").is_file():
            return UPDATE_GUIDE
        return capability["skill"]
    except (OSError, ValueError, TypeError, RuntimeError):
        return UPDATE_GUIDE


def baseline_path() -> Path:
    """Find the baseline beside the managed helper or one directory above it."""
    helper_dir = Path(__file__).resolve().parent
    for candidate in (helper_dir / BASELINE, helper_dir.parent / BASELINE):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise ValueError("installed baseline not found")


def baseline_id(path: Path) -> str:
    with path.open("rb") as handle:
        content = handle.read(MAX_BASELINE_BYTES + 1)
    if not content or len(content) > MAX_BASELINE_BYTES:
        raise ValueError("installed baseline has an invalid size")
    text = content.decode("utf-8")
    matches = list(BASELINE_ID_RE.finditer(text))
    if len(matches) != 1:
        raise ValueError("installed baseline has no unique baseline ID")
    return matches[0].group("id")


def session_context(part: int) -> dict:
    """Load only this installation, with an explicit process-local opt-out.

    Four bounded outputs keep the complete baseline below Claude's per-hook
    character limit and Codex's configured context limit. No state is written.
    A bad value or unreadable baseline stops the session instead of disabling it.
    """
    disabled = os.environ.get("AISCB_DISABLE", "0")
    if disabled not in {"0", "1"}:
        return {"continue": False, "stopReason": "AISCB_DISABLE must be 0 or 1."}
    try:
        path = baseline_path()
        identifier = baseline_id(path)
        with path.open("rb") as handle:
            raw = handle.read(MAX_BASELINE_BYTES + 1)
        if len(raw) > MAX_BASELINE_BYTES:
            raise ValueError("baseline too large")
        content = raw.decode("utf-8")
        if len(content) > SESSION_PARTS * SESSION_PART_CHARS:
            raise ValueError("baseline exceeds session context capacity")
    except (OSError, UnicodeDecodeError, ValueError):
        return {"continue": False, "stopReason": "Could not load the AI Secure Coding Baseline; repair this installation."}
    scope = str(path)
    if disabled == "1":
        message = f"AI Secure Coding Baseline disabled for this installation: {scope} (AISCB_DISABLE=1)."
        context = (
            f"aiscb-session-disabled: {scope}\n"
            "This installation supplies no baseline rules for this session. "
            "Other instruction sources still apply. Do not load this installation's "
            "baseline unless the user explicitly requests it. A baseline already "
            "in conversation history remains there; use a fresh session to exclude it."
        )
    else:
        message = f"AI Secure Coding Baseline active: {identifier}"
        context = (
            f"aiscb-session-part: {part + 1}/{SESSION_PARTS}; source: {scope}\n"
            "Apply the baseline supplied by these parts.\n\n"
            + content[part * SESSION_PART_CHARS:(part + 1) * SESSION_PART_CHARS]
        )
    if len(context) >= 9500:
        return {"continue": False, "stopReason": "Baseline context exceeds the hook output limit."}
    result = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    if part == 0:
        result["systemMessage"] = message
    return result


def release_order(identifier: str) -> tuple[str, tuple[int, ...]] | None:
    """Split a baseline ID into its name and the release numbers to compare."""
    match = RELEASE_RE.fullmatch(identifier)
    if match is None:
        return None
    release = match.group("version").split("-", 1)[0].split("+", 1)[0]
    return match.group("name"), tuple(int(part) for part in release.split("."))


def installer_path(helper_dir: Path, home: Path) -> Path | None:
    for candidate in (helper_dir / INSTALLER, home / USER_DATA / INSTALLER):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def read_update_check(path: Path) -> dict | None:
    if path.is_symlink() or not path.is_file():
        return None
    with path.open("rb") as handle:
        raw = handle.read(MAX_REGISTRY_BYTES + 1)
    if len(raw) > MAX_REGISTRY_BYTES:
        return None
    registry = json.loads(raw.decode("utf-8"))
    section = registry.get("update_check") if isinstance(registry, dict) else None
    return section if isinstance(section, dict) else None


def refresh_in_background(checked: object, installer: Path) -> None:
    """Let the installer look up the release without holding up this session."""
    if isinstance(checked, bool) or not isinstance(checked, int):
        checked = 0
    if time.time() - checked < CHECK_INTERVAL:
        return
    subprocess.Popen(
        [sys.executable, str(installer), "--refresh-update-cache"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def update_note(installed: str, helper_dir: Path, home: Path, *, claude: bool = False) -> str:
    """Describe the cached release check without claiming a check that never ran.

    A newer-release note is a pointer, never a command: it lands in an agent's
    session, and the update runs from a terminal and takes effect in the next
    session.
    """
    section = read_update_check(home / REGISTRY)
    if section is None:
        return "update status not checked"
    installer = installer_path(helper_dir, home)
    if section.get("enabled") is True and installer is not None:
        refresh_in_background(section.get("checked"), installer)
    latest = section.get("latest")
    if not isinstance(latest, str):
        return "update status not checked"
    published = release_order(latest)
    current = release_order(installed)
    if published is None or current is None:
        return "update status not checked"
    checked = section.get("checked")
    checked_on = (
        time.strftime("%Y-%m-%d", time.gmtime(checked))
        if isinstance(checked, int) and not isinstance(checked, bool) and 0 <= checked
        else None
    )
    date = f" (checked {checked_on})" if checked_on else ""
    stale = (
        "; check stale"
        if checked_on and time.time() - checked >= CHECK_INTERVAL
        else ""
    )
    if published[0] != current[0]:
        return "update status not checked"
    if published[1] > current[1]:
        return (
            f"update {latest[len(published[0]) + 1:]} available{date}{stale}: "
            f"{update_guide(home, Path.cwd(), claude=claude)}"
        )
    if checked_on:
        return f"no newer release known at last check{date}{stale}"
    return "update status not checked"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-context", action="store_true",
        help="load the baseline for a switchable installation (AISCB_DISABLE=1 opts out)",
    )
    parser.add_argument("--session-check", action="store_true",
                        help="block a prompt when the session loader cannot supply valid context")
    parser.add_argument("--part", type=int, choices=range(SESSION_PARTS))
    parser.add_argument(
        "--output",
        choices=("message", "json", "copilot"),
        default="message",
        help="plain startup banner or tool-specific hook JSON",
    )
    args = parser.parse_args(argv)
    if args.session_check:
        if args.session_context or args.part is not None:
            parser.error("--session-check takes no context or part option")
        result = session_context(0)
        if result.get("continue") is False:
            print(json.dumps({"decision": "block", "reason": result["stopReason"],
                              "continue": False, "stopReason": result["stopReason"]}))
        else:
            print("{}")
        return 0
    if args.session_context:
        if args.part is None:
            parser.error("--session-context requires --part")
        result = session_context(args.part)
        if args.part == 0 and "systemMessage" in result:
            try:
                note = update_note(
                    baseline_id(baseline_path()), Path(__file__).resolve().parent, Path.home(),
                    claude=bool(os.environ.get("CLAUDE_PROJECT_DIR"))
                )
            except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
                note = "update status not checked"
            if note:
                result["systemMessage"] += f" — {note}"
        print(json.dumps(result))
        return 0
    if args.part is not None:
        parser.error("--part requires --session-context")
    try:
        installed = baseline_id(baseline_path())
    except (OSError, UnicodeDecodeError, ValueError):
        print("Could not read the installed AI Secure Coding Baseline ID.", file=sys.stderr)
        return 1
    message = f"AI Secure Coding Baseline active: {installed}"
    try:
        note = update_note(installed, Path(__file__).resolve().parent, Path.home(),
                           claude=bool(os.environ.get("CLAUDE_PROJECT_DIR")))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        note = "update status not checked"
    if note:
        message = f"{message} — {note}"

    if args.output == "json":
        print(json.dumps({"systemMessage": message}))
    elif args.output == "copilot":
        print(json.dumps({"type": "progress", "message": message, "temporary": False}))
        print("{}")
    else:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

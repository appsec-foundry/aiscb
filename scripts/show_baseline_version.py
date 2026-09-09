#!/usr/bin/env python3
"""Print the installed baseline ID for agent session-start hooks."""

import argparse
import json
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


def update_note(installed: str, helper_dir: Path, home: Path) -> str:
    """Name the newer release the installer cached and where the update is described.

    The note is a pointer, never a command: it lands in an agent's session,
    and the update runs from a terminal and takes effect in the next session.
    """
    section = read_update_check(home / REGISTRY)
    if section is None:
        return ""
    installer = installer_path(helper_dir, home)
    if section.get("enabled") is True and installer is not None:
        refresh_in_background(section.get("checked"), installer)
    latest = section.get("latest")
    if not isinstance(latest, str):
        return ""
    published = release_order(latest)
    current = release_order(installed)
    if published is None or current is None:
        return ""
    if published[0] != current[0] or published[1] <= current[1]:
        return ""
    return f"Update {latest[len(published[0]) + 1:]} available: {UPDATE_GUIDE}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        choices=("message", "json"),
        default="message",
        help="plain startup banner or hook JSON with a visible system message",
    )
    args = parser.parse_args(argv)
    try:
        installed = baseline_id(baseline_path())
    except (OSError, UnicodeDecodeError, ValueError):
        print("Could not read the installed AI Secure Coding Baseline ID.", file=sys.stderr)
        return 1
    message = f"AI Secure Coding Baseline active: {installed}"
    try:
        note = update_note(installed, Path(__file__).resolve().parent, Path.home())
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        note = ""
    if note:
        message = f"{message}\n{note}"

    if args.output == "json":
        print(json.dumps({"systemMessage": message}))
    else:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

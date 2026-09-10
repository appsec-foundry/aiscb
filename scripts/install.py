#!/usr/bin/env python3
"""Install, discover, and update the baseline without overwriting user work."""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import Callable

BASELINE = "secure-coding-baseline.md"
VERSION_HOOK_DIR = ".aiscb"
VERSION_HOOK_NAME = "show-baseline-version.py"
INSTALLER_NAME = "install.py"
SESSION_LOADER_NAME = "session-loader.md"
SESSION_PARTS = 4
PREVIOUS_DATA_DIR_NAME = "ai-secure-coding-baseline"
INSTALLER_SOURCE = Path(__file__).resolve()
# A checkout and the remote bundle keep this file in scripts/, with the baseline
# one level above. The copy placed beside an installed baseline sits next to it,
# so an update needs no checkout.
if INSTALLER_SOURCE.parent.name == "scripts":
    REPO = INSTALLER_SOURCE.parent.parent
    VERSION_HOOK_SOURCE = INSTALLER_SOURCE.parent / "show_baseline_version.py"
    LOCAL_ORIGIN = "bundled checkout"
else:
    REPO = INSTALLER_SOURCE.parent
    VERSION_HOOK_SOURCE = REPO / VERSION_HOOK_NAME
    LOCAL_ORIGIN = "installed copy"
SOURCE = REPO / BASELINE
# SHA-256 of every hook helper this installer has shipped, the current one last.
# Only an unchanged copy of one of these is replaced, so edited or foreign code
# in that place survives. Append the new digest whenever the helper changes.
KNOWN_HOOK_DIGESTS = (
    "b43737769f40c85ff056e6e237b7b3035a1617eddf9a4269b92c8bd8ba78b182",
    "3e0961143718b21cc16317ef63a5ce6d4a34dcf91bda7ad6577f160e4927f89d",
    "9ab4a0107dec2cac076c75a0eedb0c768a18846b60a33851550544a656b249ba",
    "768746c35676ebf701e7c43fce26ff000dd1f4754e7e060f6f280510e1cd0033",
    "f0475757fec0495b0558f0988751338169d1047e7ddbc27d59678d9c0f1ff91e",
    "7f957e239e7397587781c1498b85db20dad608c5ba1caebfa1d8696673370a9e",
    "fc6fe42137868f7024df6cf340fa375380150ed5aa12eda2b3bee2cfae93eaa7",
    "b2fa3d5d1d9d891117ca9b035db243129d24b6eb0c2c54c3568eef623f83bdea",
)
COPILOT_VERSION_HOOK_NAME = "aiscb-baseline-version.json"
PREVIOUS_COPILOT_VERSION_HOOK_NAME = "aisec-baseline-version.json"
TOOLS = ("claude", "codex", "copilot")
TOOL_LABELS = {
    "claude": "Claude Code",
    "codex": "Codex",
    "copilot": "GitHub Copilot",
}

OFFICIAL_NAME = "aiscb"
GITHUB_REPOSITORY = "appsec-foundry/aiscb"
LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
)
CONTENTS_ROOT_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/contents"
API_VERSION = "2026-03-10"
ONLINE_TIMEOUT = 4
MAX_BASELINE_BYTES = 256 * 1024
MAX_INSTRUCTION_BYTES = 512 * 1024
MAX_INSTALLER_BYTES = 512 * 1024
MAX_API_BYTES = 512 * 1024
MAX_REGISTRY_BYTES = 128 * 1024
MAX_HOOK_CONFIG_BYTES = 128 * 1024
MAX_PROJECTS = 200
REGISTRY_SCHEMA = 1
UPDATE_CHECK_KEY = "update_check"
QUICK_START_URL = f"https://github.com/{GITHUB_REPOSITORY}#quick-start"

# A signed manifest lets an installed copy verify a later bundle without the
# Quick start: the release tag names the version, the manifest pins every file,
# and the signature binds the manifest to a release key this installer carries.
MANIFEST_NAME = "bundle.json"
SIGNATURE_NAME = "bundle.json.sig"
MANIFEST_SCHEMA = 1
SIGNATURE_NAMESPACE = "aiscb-bundle"
SIGNER_PRINCIPAL = "aiscb-release"
# OpenSSH allowed_signers lines for the keys that may sign a bundle manifest.
# A rotated key ships here in a new bundle; a copy that predates it verifies
# nothing signed by the new key and needs the current Quick start once.
ALLOWED_SIGNERS: tuple[str, ...] = (
    "aiscb-release ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILd3kACJfPJk7lcPr79sDqWlq3o552E1+KhaPNmnsboD",
)
BUNDLE_FILES = {
    BASELINE: MAX_BASELINE_BYTES,
    "scripts/install.py": MAX_INSTALLER_BYTES,
    "scripts/show_baseline_version.py": MAX_BASELINE_BYTES,
}
MAX_MANIFEST_BYTES = 16 * 1024
MAX_SIGNATURE_BYTES = 8 * 1024
SIGNATURE_HEADER = b"-----BEGIN SSH SIGNATURE-----"
SSH_KEYGEN_TIMEOUT = 20

SEMVER_TEXT = (
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
BASELINE_ID_RE = re.compile(
    rf"^`baseline-id:\s*(?P<name>[a-z][a-z0-9-]*)-"
    rf"(?P<version>{SEMVER_TEXT})`",
    re.MULTILINE,
)
RELEASE_TAG_RE = re.compile(
    rf"^(?:v|{OFFICIAL_NAME}-)?(?P<version>{SEMVER_TEXT})$"
)


@total_ordering
@dataclass(frozen=True, eq=False)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    metadata: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = re.fullmatch(
            r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\."
            r"(?P<patch>0|[1-9]\d*)"
            r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
            r"(?:\+(?P<meta>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?",
            value,
        )
        if not match:
            raise ValueError("invalid semantic version")
        prerelease = tuple((match.group("pre") or "").split("."))
        metadata = tuple((match.group("meta") or "").split("."))
        if any(item.isdigit() and len(item) > 1 and item.startswith("0") for item in prerelease):
            raise ValueError("numeric prerelease identifiers cannot have leading zeroes")
        return cls(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            tuple(item for item in prerelease if item),
            tuple(item for item in metadata if item),
        )

    def _core(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._core() == other._core() and self.prerelease == other.prerelease

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        if self._core() != other._core():
            return self._core() < other._core()
        if not self.prerelease:
            return False
        if not other.prerelease:
            return True
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            left_numeric, right_numeric = left.isdigit(), right.isdigit()
            if left_numeric and right_numeric:
                return int(left) < int(right)
            if left_numeric != right_numeric:
                return left_numeric
            return left < right
        return len(self.prerelease) < len(other.prerelease)

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += "-" + ".".join(self.prerelease)
        if self.metadata:
            value += "+" + ".".join(self.metadata)
        return value


@dataclass(frozen=True)
class Baseline:
    name: str
    version: SemVer
    content: bytes
    origin: str

    @property
    def baseline_id(self) -> str:
        return f"{self.name}-{self.version}"

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def is_official(self) -> bool:
        return self.name == OFFICIAL_NAME and not self.version.metadata


@dataclass(frozen=True)
class Installation:
    kind: str
    root: Path
    source: Path
    baseline: Baseline
    tools: tuple[str, ...]
    tracked_digest: str | None = None

    @property
    def label(self) -> str:
        if self.kind == "project":
            return f"project {display_path(self.root)}"
        if self.kind == "user":
            return "user-wide"
        if self.kind == "legacy-user":
            return f"user-wide (linked to {display_path(self.source.parent)})"
        return f"unmanaged file {display_path(self.source)}"

    def has_update(self, available: Baseline) -> bool:
        return (
            self.kind != "unmanaged"
            and self.baseline.is_official
            and (
                self.baseline.version < available.version
                or (
                    self.baseline.version == available.version
                    and self.baseline.digest != available.digest
                )
            )
        )


def display_path(path: Path) -> str:
    """Quote paths so control characters cannot alter terminal output."""
    return repr(str(path))


def parse_baseline(content: bytes, origin: str) -> Baseline:
    if not content or len(content) > MAX_INSTRUCTION_BYTES:
        raise ValueError("baseline content has an invalid size")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("baseline content is not UTF-8") from error
    matches = list(BASELINE_ID_RE.finditer(text))
    if len(matches) != 1:
        raise ValueError("expected exactly one baseline-id")
    match = matches[0]
    return Baseline(
        match.group("name"),
        SemVer.parse(match.group("version")),
        content,
        origin,
    )


def read_limited(path: Path, limit: int) -> bytes:
    with path.open("rb") as handle:
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise ValueError("file is too large")
    return content


def read_baseline(path: Path) -> Baseline:
    return parse_baseline(read_limited(path, MAX_INSTRUCTION_BYTES), str(path))


def bundled_baseline() -> Baseline:
    return parse_baseline(read_limited(SOURCE, MAX_BASELINE_BYTES), LOCAL_ORIGIN)


class _GitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        destination = urllib.parse.urlsplit(new_url)
        if destination.scheme != "https" or destination.netloc != "api.github.com":
            raise urllib.error.HTTPError(
                new_url, code, "refused cross-host update redirect", headers, file_pointer
            )
        return super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )


def _read_json_url(url: str) -> object:
    destination = urllib.parse.urlsplit(url)
    if destination.scheme != "https" or destination.netloc != "api.github.com":
        raise ValueError("unexpected update server")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "aiscb-setup",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    opener = urllib.request.build_opener(_GitHubRedirectHandler())
    with opener.open(request, timeout=ONLINE_TIMEOUT) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or final.netloc != "api.github.com":
            raise ValueError("unexpected update server")
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_API_BYTES:
            raise ValueError("update response is too large")
        payload = response.read(MAX_API_BYTES + 1)
    if len(payload) > MAX_API_BYTES:
        raise ValueError("update response is too large")
    return json.loads(payload.decode("utf-8"))


def fetch_release_tag(
    fetch_json: Callable[[str], object] = _read_json_url,
) -> tuple[str, SemVer]:
    """Name the latest stable release and the version its tag carries."""
    release = fetch_json(LATEST_RELEASE_URL)
    if not isinstance(release, dict):
        raise ValueError("invalid release response")
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("latest release is not stable")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or len(tag) > 100:
        raise ValueError("release has no valid tag")
    tag_match = RELEASE_TAG_RE.fullmatch(tag)
    if not tag_match:
        raise ValueError("release tag does not contain a supported version")
    return tag, SemVer.parse(tag_match.group("version"))


def fetch_release_file(
    fetch_json: Callable[[str], object], path: str, ref: str, limit: int
) -> bytes:
    """Read one file of the release tree through the contents API."""
    query = urllib.parse.urlencode({"ref": ref})
    payload = fetch_json(f"{CONTENTS_ROOT_URL}/{path}?{query}")
    if not isinstance(payload, dict) or payload.get("type") != "file":
        raise ValueError(f"release {path} is not a file")
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        raise ValueError(f"release {path} has an unsupported encoding")
    try:
        encoded = "".join(payload["content"].splitlines())
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError(f"release {path} is not valid base64") from error
    if len(content) > limit:
        raise ValueError(f"release {path} is too large")
    return content


def fetch_release_baseline(
    fetch_json: Callable[[str], object] = _read_json_url,
) -> Baseline:
    tag, tag_version = fetch_release_tag(fetch_json)
    content = fetch_release_file(fetch_json, BASELINE, tag, MAX_BASELINE_BYTES)
    baseline = parse_baseline(content, f"GitHub release {tag}")
    if not baseline.content.startswith(b"# AI Secure Coding Baseline\n"):
        raise ValueError("release baseline has an unexpected format")
    if not baseline.is_official or baseline.version != tag_version:
        raise ValueError("release tag and baseline-id do not match")
    return baseline


def latest_available(check_online: bool) -> tuple[Baseline, str, Baseline | None]:
    """Return the baseline to install, a note for the origin line, and the release."""
    bundled = bundled_baseline()
    if not check_online:
        return bundled, ", online check skipped", None
    try:
        released = fetch_release_baseline()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return bundled, ", no published release", None
        return bundled, ", online check unavailable", None
    except (OSError, ValueError, json.JSONDecodeError):
        return bundled, ", online check unavailable", None
    if bundled.version > released.version:
        return bundled, f", newer than published {released.version}", released
    return released, "", released


def project_targets(root: Path) -> dict[str, list[tuple[str, Path]]]:
    return {
        "claude": [("link", root / ".claude" / "rules" / BASELINE)],
        "codex": [("link", root / "AGENTS.md")],
        "copilot": [("link", root / ".github" / "copilot-instructions.md")],
    }


def user_data_root(home: Path) -> Path:
    return home / ".local" / "share" / "aiscb"


def previous_user_data_root(home: Path) -> Path:
    return home / ".local" / "share" / PREVIOUS_DATA_DIR_NAME


def user_source(home: Path) -> Path:
    return user_data_root(home) / BASELINE


def user_targets(home: Path) -> dict[str, list[tuple[str, Path]]]:
    return {
        "claude": [
            ("link", home / ".claude" / BASELINE),
            ("import_line", home / ".claude" / "CLAUDE.md"),
        ],
        "codex": [("link", home / ".codex" / "AGENTS.md")],
        "copilot": [("link", home / ".copilot" / "copilot-instructions.md")],
    }


def link_text(target: Path, source: Path, *, relative: bool) -> str:
    """Inside a project the link stays relative, so a clone keeps working."""
    return os.path.relpath(source, target.parent) if relative else str(source)


def _write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(content)
    except BaseException:
        if created and path.exists() and not path.is_symlink():
            path.unlink()
        raise


def _atomic_replace(path: Path, content: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def place_baseline(
    root: Path,
    report: list[str],
    content: bytes | None = None,
    *,
    create_root: bool = False,
) -> Path | None:
    """Place one real baseline file, refusing foreign or invalid occupants."""
    local = root / BASELINE
    if local.resolve() == SOURCE.resolve():
        return local
    if local.is_symlink():
        report.append(f"blocked {local}: is a symlink, inspect it first")
        return None
    if local.exists():
        if not local.is_file():
            report.append(f"blocked {local}: is not a regular file")
            return None
        try:
            read_baseline(local)
        except (OSError, ValueError):
            report.append(f"blocked {local}: exists but is not a valid baseline")
            return None
        return local
    payload = content if content is not None else bundled_baseline().content
    if not root.is_dir():
        if not create_root:
            report.append(f"blocked {root}: project directory does not exist")
            return None
        root.mkdir(parents=True, exist_ok=True)
    _write_new(local, payload)
    report.append(f"added {local}")
    return local


def install_link(
    target: Path,
    source: Path,
    report: list[str],
    *,
    relative: bool,
) -> None:
    link = link_text(target, source, relative=relative)
    if target.is_symlink():
        if _session_link(target, source):
            report.append(f"in place {target} (session switch)")
            return
        if Path(os.readlink(target)) == Path(link):
            report.append(f"in place {target}")
            return
        report.append(f"blocked {target}: points elsewhere, remove it first")
        return
    if target.exists():
        report.append(
            f"blocked {target}: exists — append {source.name} to it by hand"
        )
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(link)
    report.append(f"linked {target} -> {link}")


def _instruction_lines(target: Path) -> list[str]:
    content = read_limited(target, MAX_INSTRUCTION_BYTES)
    return content.decode("utf-8").splitlines()


def install_import_line(
    target: Path,
    source: Path,
    report: list[str],
    *,
    accepted_sources: tuple[Path, ...] = (),
) -> None:
    line = f"@{source}"
    if target.exists():
        try:
            lines = _instruction_lines(target)
        except (OSError, UnicodeDecodeError, ValueError):
            report.append(f"blocked {target}: cannot safely read existing file")
            return
        accepted_lines = {line, *(f"@{item}" for item in accepted_sources)}
        if any(item in lines for item in accepted_lines):
            report.append(f"in place {target}")
        else:
            report.append(f"blocked {target}: exists — add the line {line!r} by hand")
        return
    if target.is_symlink():
        report.append(f"blocked {target}: is a broken symlink")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_new(target, f"{line}\n".encode())
    report.append(f"wrote {target}")


def install(
    tools: list[str],
    root: Path,
    home: Path | None,
    *,
    content: bytes | None = None,
) -> list[str]:
    report: list[str] = []
    if home is not None:
        targets = user_targets(home)
        source = place_baseline(
            user_data_root(home), report, content, create_root=True
        )
        relative = False
    else:
        targets = project_targets(root)
        source = place_baseline(root, report, content)
        relative = True
    if source is None:
        return report
    if home is not None:
        _place_installer(home, report)
        _place_version_hook(root, home, report)

    for tool in tools:
        actions = targets[tool]
        if not actions:
            report.append(f"skipped {tool}: no documented location for this scope")
            continue
        for kind, target in actions:
            if kind == "link":
                install_link(target, source, report, relative=relative)
            else:
                accepted_sources = (
                    (targets[tool][0][1],) if home is not None and tool == "claude"
                    else ()
                )
                install_import_line(
                    target,
                    source,
                    report,
                    accepted_sources=accepted_sources,
                )
    return report


def _place_installer(home: Path, report: list[str]) -> Path | None:
    """Keep a runnable installer beside the baseline, so updates need no checkout."""
    target = user_data_root(home) / INSTALLER_NAME
    if target == INSTALLER_SOURCE:
        report.append(f"in place {target}")
        return target
    content = read_limited(INSTALLER_SOURCE, MAX_INSTALLER_BYTES)
    if target.is_symlink():
        report.append(f"blocked {target}: is a symlink")
        return None
    if target.exists():
        if not target.is_file():
            report.append(f"blocked {target}: is not a regular file")
            return None
        try:
            current = read_limited(target, MAX_INSTALLER_BYTES)
        except (OSError, ValueError):
            report.append(f"blocked {target}: cannot safely read existing installer")
            return None
        if current == content:
            report.append(f"in place {target}")
            return target
        try:
            _atomic_replace(target, content)
        except OSError:
            report.append(f"blocked {target}: cannot replace the installer")
            return None
        report.append(f"updated {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_new(target, content)
    report.append(f"added {target}")
    return target


def version_hook_path(root: Path, home: Path | None) -> Path:
    if home is not None:
        return user_data_root(home) / VERSION_HOOK_NAME
    return root / VERSION_HOOK_DIR / VERSION_HOOK_NAME


def _place_version_hook(root: Path, home: Path | None, report: list[str]) -> Path | None:
    target = version_hook_path(root, home)
    try:
        content = read_limited(VERSION_HOOK_SOURCE, MAX_BASELINE_BYTES)
    except (OSError, ValueError):
        report.append(f"blocked {target}: the hook helper source is missing")
        return None
    if target.is_symlink():
        report.append(f"blocked {target}: is a symlink")
        return None
    if target.exists():
        if not target.is_file():
            report.append(f"blocked {target}: is not a regular file")
            return None
        try:
            current = read_limited(target, MAX_BASELINE_BYTES)
        except (OSError, ValueError):
            report.append(f"blocked {target}: cannot safely read existing hook helper")
            return None
        if current != content:
            if hashlib.sha256(current).hexdigest() not in KNOWN_HOOK_DIGESTS:
                report.append(f"blocked {target}: contains different hook helper code")
                return None
            try:
                _atomic_replace(target, content)
            except OSError:
                report.append(f"blocked {target}: cannot replace the hook helper")
                return None
            report.append(f"updated {target}")
            return target
        report.append(f"in place {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_new(target, content)
    report.append(f"added {target}")
    return target


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_hook_config(path: Path) -> tuple[dict[str, object], bool]:
    if path.is_symlink():
        raise ValueError("configuration is a symlink")
    if not path.exists():
        return {}, False
    if not path.is_file():
        raise ValueError("configuration is not a regular file")
    content = read_limited(path, MAX_HOOK_CONFIG_BYTES)
    parsed = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_json_object)
    if not isinstance(parsed, dict):
        raise ValueError("configuration is not a JSON object")
    return parsed, True


def _write_hook_config(path: Path, config: dict[str, object], existed: bool) -> None:
    payload = (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode()
    if len(payload) > MAX_HOOK_CONFIG_BYTES:
        raise ValueError("hook configuration is too large")
    path.parent.mkdir(parents=True, exist_ok=True)
    if existed:
        _atomic_replace(path, payload)
    else:
        _write_new(path, payload)


def _without_helper_path(value: object) -> object:
    """Blank out the helper's location, so two entries compare by their shape."""
    if isinstance(value, str):
        return "<helper>" if VERSION_HOOK_NAME in value else value
    if isinstance(value, list):
        return [_without_helper_path(item) for item in value]
    if isinstance(value, dict):
        return {key: _without_helper_path(item) for key, item in value.items()}
    return value


def _is_moved_version_hook(existing: object, entry: dict[str, object]) -> bool:
    """An entry this installer wrote for a helper that has since moved."""
    # Session hooks carry part numbers and a validation command. Comparing only
    # their shape would discard those arguments and accept customized commands.
    if "--session-context" in json.dumps(entry) or "--session-check" in json.dumps(entry):
        return existing == entry
    return (
        VERSION_HOOK_NAME in json.dumps(existing, ensure_ascii=False)
        and _without_helper_path(existing) == _without_helper_path(entry)
    )


def _install_merged_version_hook(
    path: Path,
    event: str,
    entry: dict[str, object],
    report: list[str],
) -> None:
    moved: list[int] = []
    try:
        config, existed = _read_hook_config(path)
        hooks = config.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks is not an object")
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            raise ValueError(f"{event} is not a list")
        if entry in entries:
            report.append(f"in place {path}")
            return
        moved = [
            index
            for index, existing in enumerate(entries)
            if _is_moved_version_hook(existing, entry)
        ]
        if VERSION_HOOK_NAME in json.dumps(entries, ensure_ascii=False) and not moved:
            report.append(
                f"blocked {path}: contains a different baseline version hook; "
                "remove it to let setup write the current one"
            )
            return
        if moved:
            entries[moved[0]] = entry
            for index in reversed(moved[1:]):
                del entries[index]
        else:
            entries.append(entry)
        _write_hook_config(path, config, existed)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        report.append(f"blocked {path}: cannot safely merge the version hook")
        return
    if moved:
        report.append(f"updated {path}: the hook now reads the current helper")
        return
    report.append(f"updated {path}" if existed else f"wrote {path}")


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _session_loader(source: Path, helper: Path) -> bytes:
    project = helper.parent != source.parent
    location = BASELINE if project else str(source)
    script = f"{VERSION_HOOK_DIR}/{VERSION_HOOK_NAME}" if project else str(helper)
    command = f"python3 {shlex.quote(script)} --session-context --part"
    return (
        "# AI Secure Coding Baseline session loader\n\n"
        "This installation uses a conditional loader. Before working, check for "
        f"all {SESSION_PARTS} `aiscb-session-part` markers or an "
        "`aiscb-session-disabled` marker for this installation in your context. "
        f"Its baseline source is `{location}` (relative to the project root "
        "for a project installation). Apply the supplied baseline parts when active.\n\n"
        "If the markers are missing, the startup hook did not load. Run each of "
        f"the following commands from the project root, for parts 0 through {SESSION_PARTS - 1}:\n\n"
        f"```sh\n{command} 0\n{command} 1\n{command} 2\n{command} 3\n```\n\n"
        "Use `py -3` instead of `python3` on Windows. Follow the returned "
        "`additionalContext`; if any result has `continue: false`, a command "
        "fails, or the output is incomplete, stop and report the loader failure. "
        "Do not assume the baseline is disabled. A disabled result applies only "
        "to this installation; keep all other instructions. Never alter "
        "AISCB_DISABLE yourself to bypass the loader.\n"
    ).encode()


def _session_link(target: Path, source: Path) -> bool:
    if not target.is_symlink():
        return False
    for directory in (source.parent, source.parent / VERSION_HOOK_DIR):
        loader = directory / SESSION_LOADER_NAME
        if target.resolve(strict=False) != loader.resolve(strict=False):
            continue
        if loader.is_symlink() or not loader.is_file():
            return False
        try:
            return read_limited(loader, MAX_INSTRUCTION_BYTES) == _session_loader(
                source, directory / VERSION_HOOK_NAME
            )
        except (OSError, ValueError):
            return False
    return False


def _instruction_source(target: Path) -> Path:
    resolved = target.resolve(strict=False)
    if resolved.name == SESSION_LOADER_NAME:
        directory = resolved.parent
        if directory.name == VERSION_HOOK_DIR:
            directory = directory.parent
        source = directory / BASELINE
        if _session_link(target, source):
            return source
    return resolved


def _session_hook(tool: str, helper: Path, project: bool) -> dict[str, object]:
    if project:
        script = f"{VERSION_HOOK_DIR}/{VERSION_HOOK_NAME}"
        command = (
            f'python3 "${{CLAUDE_PROJECT_DIR}}/{script}"' if tool == "claude"
            else f'python3 "$(git rev-parse --show-toplevel)/{script}"'
        )
        windows = f'py -3 "$(git rev-parse --show-toplevel)/{script}"'
    else:
        command = f"python3 {shlex.quote(str(helper))}"
        windows = f"py -3 {_powershell_quote(str(helper))}"
    handlers = []
    for part in range(SESSION_PARTS):
        suffix = f" --session-context --part {part}"
        handler = {"type": "command", "command": command + suffix, "timeout": 5}
        if tool == "codex":
            handler.update(commandWindows=windows + suffix, additionalContextLimit=6000)
        handlers.append(handler)
    return {"matcher": "startup|resume|fork|clear|compact", "hooks": handlers}


def _session_hook_path(tool: str, root: Path, home: Path | None) -> Path:
    directory = (home or root) / f".{tool}"
    return directory / ("settings.json" if tool == "claude" else "hooks.json")


def _session_check_hook(tool: str, helper: Path, project: bool) -> dict[str, object]:
    handler = dict(_session_hook(tool, helper, project)["hooks"][0])
    for key in ("command", "commandWindows"):
        if key in handler:
            handler[key] = handler[key].replace("--session-context --part 0", "--session-check")
    handler.pop("additionalContextLimit", None)
    return {"hooks": [handler]}


def _check_session_parents(path: Path, scope: Path) -> None:
    """A repository link must not redirect setup into another tool's settings."""
    for parent in path.parents:
        if parent == scope:
            return
        if parent.is_symlink():
            raise ValueError("a session installation directory is a symlink")
    raise ValueError("session installation path is outside the selected scope")


def install_session_switch(tools: list[str], root: Path, home: Path | None) -> list[str]:
    """Opt in explicitly; migrate only exact managed links and import lines.

    Prepare hooks before redirecting instructions. A failed preparation leaves
    static instructions active. No files are changed when a session starts.
    """
    if not tools or any(tool not in {"claude", "codex"} for tool in tools):
        return ["blocked session switch: choose claude and/or codex"]
    report: list[str] = []
    source = user_source(home) if home is not None else root / BASELINE
    targets = user_targets(home) if home is not None else project_targets(root)
    helper = version_hook_path(root, home)
    loader = helper.parent / SESSION_LOADER_NAME
    loader_content = _session_loader(source, helper)
    plans = []
    try:
        if any(ord(char) < 32 or char == "`" for char in str(source) + str(helper)):
            raise ValueError("path cannot be represented in loader instructions")
        for path in (source, helper, loader):
            _check_session_parents(path, home or root)
        if source.exists():
            if source.is_symlink():
                raise ValueError("baseline source is a symlink")
            baseline = read_baseline(source)
        else:
            baseline = bundled_baseline()
        if len(baseline.content.decode("utf-8")) > SESSION_PARTS * 7000:
            raise ValueError("baseline exceeds session context capacity")
        if loader.is_symlink() or (loader.exists() and read_limited(loader, MAX_INSTRUCTION_BYTES) != loader_content):
            raise ValueError("loader contains different content")
        for tool in tools:
            target = targets[tool][0][1]
            for _, path in targets[tool]:
                _check_session_parents(path, home or root)
            if target.exists() or target.is_symlink():
                if not _link_points_to(target, source) and not _session_link(target, source):
                    raise ValueError("an instruction file is not an exact managed link")
            path = _session_hook_path(tool, root, home)
            _check_session_parents(path, home or root)
            config, existed = _read_hook_config(path)
            if config.get("disableAllHooks") is True:
                raise ValueError("hooks are disabled in the selected settings")
            hooks = config.setdefault("hooks", {})
            if not isinstance(hooks, dict):
                raise ValueError("invalid hooks configuration")
            entries = hooks.setdefault("SessionStart", [])
            if not isinstance(entries, list):
                raise ValueError("invalid SessionStart hooks")
            legacy = (_claude_version_hook if tool == "claude" else _codex_version_hook)(helper, home is None)
            entry = _session_hook(tool, helper, home is None)
            kept = []
            for item in entries:
                if _is_moved_version_hook(item, legacy) or item == entry:
                    continue
                if VERSION_HOOK_NAME in json.dumps(item):
                    raise ValueError("a baseline hook was customized")
                kept.append(item)
            hooks["SessionStart"] = kept + [entry]
            checks = hooks.setdefault("UserPromptSubmit", [])
            check_entry = _session_check_hook(tool, helper, home is None)
            if not isinstance(checks, list):
                raise ValueError("invalid UserPromptSubmit hooks")
            if any(VERSION_HOOK_NAME in json.dumps(item) and not _is_moved_version_hook(item, check_entry)
                   for item in checks):
                raise ValueError("a baseline check hook was customized")
            hooks["UserPromptSubmit"] = [item for item in checks if not _is_moved_version_hook(item, check_entry)] + [check_entry]
            import_plan = None
            if home is not None and tool == "claude":
                imported = targets[tool][1][1]
                if imported.is_symlink():
                    raise ValueError("CLAUDE.md is a symlink")
                before = read_limited(imported, MAX_INSTRUCTION_BYTES).decode("utf-8") if imported.exists() else ""
                # Keep every unrelated byte, including line endings and comments.
                old, new = f"@{source}", f"@{target}"
                lines = before.splitlines(keepends=True)
                after = "".join(new + line[len(old):] if line.rstrip("\r\n") == old else line for line in lines)
                if new not in after.splitlines():
                    after += ("\n" if after and not after.endswith("\n") else "") + new + "\n"
                import_plan = imported, after.encode()
            plans.append((target, path, config, existed, import_plan))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return [
            f"blocked session switch: {error}; "
            "the static installation is unchanged"
        ]
    if place_baseline(source.parent, report, baseline.content, create_root=True) is None:
        return report
    if home is not None and _place_installer(home, report) is None:
        return report
    if _place_version_hook(root, home, report) is None:
        return report
    try:
        if not loader.exists():
            _write_new(loader, loader_content)
        for target, path, config, existed, import_plan in plans:
            _write_hook_config(path, config, existed)
            target.parent.mkdir(parents=True, exist_ok=True)
            # os.replace changes the link atomically, never the baseline it points to.
            _atomic_symlink(target, Path(link_text(target, loader, relative=home is None)))
            if import_plan:
                imported, content = import_plan
                if imported.exists():
                    _atomic_replace(imported, content)
                else:
                    _write_new(imported, content)
            report.append(f"enabled session switch for {target}; AISCB_DISABLE=1 applies to new sessions")
    except OSError:
        report.append("blocked session switch: could not finish writing; rerun setup before starting a session")
    return report


def _claude_version_hook(helper: Path, project: bool) -> dict[str, object]:
    script = (
        f"${{CLAUDE_PROJECT_DIR}}/{VERSION_HOOK_DIR}/{VERSION_HOOK_NAME}"
        if project
        else str(helper)
    )
    return {
        "matcher": "startup|resume|fork",
        "hooks": [
            {
                "type": "command",
                "command": "python3",
                "args": [script, "--output", "json"],
                "timeout": 5,
            }
        ],
    }


def _codex_version_hook(helper: Path, project: bool) -> dict[str, object]:
    if project:
        relative = f"{VERSION_HOOK_DIR}/{VERSION_HOOK_NAME}"
        command = f'python3 "$(git rev-parse --show-toplevel)/{relative}" --output json'
        command_windows = (
            f'py -3 "$(git rev-parse --show-toplevel)/{relative}" --output json'
        )
    else:
        command = f"python3 {shlex.quote(str(helper))} --output json"
        command_windows = f"py -3 {_powershell_quote(str(helper))} --output json"
    return {
        "matcher": "startup|resume",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "commandWindows": command_windows,
                "timeout": 5,
            }
        ],
    }


def _copilot_version_config(helper: Path, project: bool) -> dict[str, object]:
    if project:
        script = f"{VERSION_HOOK_DIR}/{VERSION_HOOK_NAME}"
        bash = f"python3 {shlex.quote(script)} --output message"
        powershell = f"py -3 {_powershell_quote(script)} --output message"
        cwd: str | None = "."
    else:
        bash = f"python3 {shlex.quote(str(helper))} --output message"
        powershell = f"py -3 {_powershell_quote(str(helper))} --output message"
        cwd = None
    hook: dict[str, object] = {
        "type": "command",
        "bash": bash,
        "powershell": powershell,
        "timeoutSec": 5,
    }
    if cwd is not None:
        hook["cwd"] = cwd
    return {"version": 1, "hooks": {"sessionStart": [hook]}}


def _install_copilot_version_hook(
    path: Path, config: dict[str, object], report: list[str]
) -> None:
    try:
        current, existed = _read_hook_config(path)
        if existed:
            if current == config:
                report.append(f"in place {path}")
                return
            if not _is_moved_version_hook(current, config):
                report.append(
                    f"blocked {path}: contains different hook configuration; "
                    "remove it to let setup write the current one"
                )
                return
            _write_hook_config(path, config, True)
            report.append(f"updated {path}: the hook now reads the current helper")
            return
        _write_hook_config(path, config, False)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        report.append(f"blocked {path}: cannot safely install the version hook")
        return
    report.append(f"wrote {path}")


def _install_copilot_version_hook_with_migration(
    path: Path,
    previous: Path,
    config: dict[str, object],
    report: list[str],
) -> None:
    if not previous.exists() and not previous.is_symlink():
        _install_copilot_version_hook(path, config, report)
        return
    try:
        previous_config, existed = _read_hook_config(previous)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        report.append(f"blocked {previous}: cannot safely migrate the previous hook")
        return
    if not existed or not _is_moved_version_hook(previous_config, config):
        report.append(
            f"blocked {previous}: contains different hook configuration; "
            "remove it to let setup migrate to the current hook name"
        )
        return
    _install_copilot_version_hook(path, config, report)
    try:
        current, current_exists = _read_hook_config(path)
        if not current_exists or current != config:
            return
        previous.unlink()
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        report.append(f"blocked {previous}: could not remove the migrated hook")
        return
    report.append(f"removed {previous}: migrated to {path}")


def install_version_hooks(
    tools: list[str], root: Path, home: Path | None
) -> list[str]:
    report: list[str] = []
    helper = _place_version_hook(root, home, report)
    if helper is None:
        return report
    project = home is None
    source = user_source(home) if home is not None else root / BASELINE
    targets = user_targets(home) if home is not None else project_targets(root)
    for tool in tools:
        if tool in {"claude", "codex"} and _session_link(targets[tool][0][1], source):
            _install_merged_version_hook(
                _session_hook_path(tool, root, home), "SessionStart",
                _session_hook(tool, helper, project), report,
            )
            _install_merged_version_hook(
                _session_hook_path(tool, root, home), "UserPromptSubmit",
                _session_check_hook(tool, helper, project), report,
            )
            continue
        if tool == "claude":
            settings = (root / ".claude" / "settings.json") if project else (
                home / ".claude" / "settings.json"
            )
            _install_merged_version_hook(
                settings, "SessionStart", _claude_version_hook(helper, project), report
            )
        elif tool == "codex":
            settings = (root / ".codex" / "hooks.json") if project else (
                home / ".codex" / "hooks.json"
            )
            _install_merged_version_hook(
                settings, "SessionStart", _codex_version_hook(helper, project), report
            )
        elif tool == "copilot":
            settings = (
                root / ".github" / "hooks" / COPILOT_VERSION_HOOK_NAME
                if project
                else home / ".copilot" / "hooks" / COPILOT_VERSION_HOOK_NAME
            )
            previous_settings = (
                root / ".github" / "hooks" / PREVIOUS_COPILOT_VERSION_HOOK_NAME
                if project
                else home
                / ".copilot"
                / "hooks"
                / PREVIOUS_COPILOT_VERSION_HOOK_NAME
            )
            _install_copilot_version_hook_with_migration(
                settings,
                previous_settings,
                _copilot_version_config(helper, project),
                report,
            )
    return report


def _version_hook_is_installed(tool: str, root: Path, home: Path | None) -> bool:
    helper = version_hook_path(root, home)
    if helper.is_symlink() or not helper.is_file():
        return False
    try:
        if read_limited(helper, MAX_BASELINE_BYTES) != read_limited(
            VERSION_HOOK_SOURCE, MAX_BASELINE_BYTES
        ):
            return False
    except (OSError, ValueError):
        return False

    project = home is None
    try:
        source = user_source(home) if home is not None else root / BASELINE
        targets = user_targets(home) if home is not None else project_targets(root)
        if tool in {"claude", "codex"} and _session_link(targets[tool][0][1], source):
            config, _ = _read_hook_config(_session_hook_path(tool, root, home))
            hooks = config.get("hooks")
            if not isinstance(hooks, dict):
                return False
            starts = hooks.get("SessionStart")
            checks = hooks.get("UserPromptSubmit")
            return (
                isinstance(starts, list) and isinstance(checks, list)
                and _session_hook(tool, helper, project) in starts
                and _session_check_hook(tool, helper, project) in checks
            )
        if tool == "claude":
            path = (root / ".claude" / "settings.json") if project else (
                home / ".claude" / "settings.json"
            )
            config, _existed = _read_hook_config(path)
            hooks = config.get("hooks")
            entries = hooks.get("SessionStart") if isinstance(hooks, dict) else None
            return isinstance(entries, list) and _claude_version_hook(
                helper, project
            ) in entries
        if tool == "codex":
            path = (root / ".codex" / "hooks.json") if project else (
                home / ".codex" / "hooks.json"
            )
            config, _existed = _read_hook_config(path)
            hooks = config.get("hooks")
            entries = hooks.get("SessionStart") if isinstance(hooks, dict) else None
            return isinstance(entries, list) and _codex_version_hook(
                helper, project
            ) in entries
        if tool == "copilot":
            path = (
                root / ".github" / "hooks" / COPILOT_VERSION_HOOK_NAME
                if project
                else home / ".copilot" / "hooks" / COPILOT_VERSION_HOOK_NAME
            )
            config, _existed = _read_hook_config(path)
            return config == _copilot_version_config(helper, project)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False
    return False


def registry_path(home: Path) -> Path:
    return home / ".config" / "aiscb" / "installations.json"


def previous_registry_path(home: Path) -> Path:
    return home / ".config" / PREVIOUS_DATA_DIR_NAME / "installations.json"


def _migrated_registry_path(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.migrated")
    for number in range(1, 101):
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        candidate = path.with_name(f"{path.name}.migrated.{number}")
    raise ValueError("too many previous registry backups")


def empty_registry() -> dict[str, object]:
    return {"schema": REGISTRY_SCHEMA, "projects": {}, "user": None}


def load_registry(path: Path) -> tuple[dict[str, object], bool, str | None]:
    if not path.exists() and not path.is_symlink():
        return empty_registry(), True, None
    if path.is_symlink() or not path.is_file():
        return empty_registry(), False, "Installation registry is not a regular file."
    try:
        raw = read_limited(path, MAX_REGISTRY_BYTES)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return empty_registry(), False, "Installation registry is invalid; it was not changed."
    if not isinstance(data, dict) or data.get("schema") != REGISTRY_SCHEMA:
        return empty_registry(), False, "Installation registry has an unsupported format."
    projects = data.get("projects")
    user = data.get("user")
    if not isinstance(projects, dict) or len(projects) > MAX_PROJECTS:
        return empty_registry(), False, "Installation registry has invalid project entries."
    if user is not None and not isinstance(user, dict):
        return empty_registry(), False, "Installation registry has an invalid user entry."
    return data, True, None


def save_registry(path: Path, registry: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(registry, indent=2, sort_keys=True) + "\n").encode()
    if len(payload) > MAX_REGISTRY_BYTES:
        raise ValueError("installation registry is too large")
    if path.is_symlink():
        raise ValueError("installation registry is a symlink")
    if path.exists():
        _atomic_replace(path, payload)
        os.chmod(path, 0o600)
    else:
        _write_new(path, payload)
        os.chmod(path, 0o600)


def load_registry_with_previous(
    home: Path, path: Path
) -> tuple[dict[str, object], bool, str | None]:
    """Load current state and retain valid records from the previous location."""
    registry, writable, note = load_registry(path)
    current_path = registry_path(home)
    if (
        not writable
        or path.resolve(strict=False) != current_path.resolve(strict=False)
    ):
        return registry, writable, note

    previous_path = previous_registry_path(home)
    if not previous_path.exists() and not previous_path.is_symlink():
        return registry, writable, note
    previous, previous_writable, _previous_note = load_registry(previous_path)
    if not previous_writable:
        return (
            registry,
            writable,
            note or "The previous installation registry is invalid; it was not imported.",
        )

    changed = False
    projects = registry.get("projects")
    previous_projects = previous.get("projects")
    if isinstance(projects, dict) and isinstance(previous_projects, dict):
        for root, entry in previous_projects.items():
            if len(projects) >= MAX_PROJECTS:
                break
            if root not in projects:
                projects[root] = entry
                changed = True
    if registry.get("user") is None and isinstance(previous.get("user"), dict):
        registry["user"] = previous["user"]
        changed = True
    if UPDATE_CHECK_KEY not in registry and isinstance(
        previous.get(UPDATE_CHECK_KEY), dict
    ):
        registry[UPDATE_CHECK_KEY] = previous[UPDATE_CHECK_KEY]
        changed = True
    if changed:
        try:
            save_registry(path, registry)
        except (OSError, ValueError):
            return (
                registry,
                writable,
                note
                or "Previous installation records were found but could not be saved.",
            )
    try:
        archived = _migrated_registry_path(previous_path)
        os.replace(previous_path, archived)
    except (OSError, ValueError):
        return (
            registry,
            writable,
            note
            or "Previous installation records were imported, but their old file "
            "could not be archived.",
        )
    return (
        registry,
        writable,
        note
        or f"Imported installation records from {previous_path}; archived the old "
        f"registry as {archived}.",
    )


def update_check_enabled(registry: dict[str, object]) -> bool:
    section = registry.get(UPDATE_CHECK_KEY)
    return isinstance(section, dict) and section.get("enabled") is True


def record_update_check(registry: dict[str, object], released: Baseline) -> None:
    """Cache the published version so the startup hook reports it without asking."""
    section = registry.get(UPDATE_CHECK_KEY)
    registry[UPDATE_CHECK_KEY] = {
        **(section if isinstance(section, dict) else {}),
        "latest": released.baseline_id,
        "checked": int(time.time()),
    }


def cache_release_check(
    state_path: Path, registry: dict[str, object], released: Baseline | None
) -> bool:
    """Store a release the caller already fetched; a cache is never worth a crash."""
    if released is None:
        return False
    record_update_check(registry, released)
    try:
        save_registry(state_path, registry)
    except (OSError, ValueError):
        return False
    return True


def refresh_update_cache(*, home: Path, state_path: Path | None = None) -> int:
    """Look up the published release for the startup hook, only if that was allowed."""
    state_path = state_path or registry_path(home)
    registry, writable, _note = load_registry_with_previous(home, state_path)
    if not writable or not update_check_enabled(registry):
        return 1
    try:
        released = fetch_release_baseline()
    except (urllib.error.HTTPError, OSError, ValueError, json.JSONDecodeError):
        return 1
    return 0 if cache_release_check(state_path, registry, released) else 1


@dataclass(frozen=True)
class Manifest:
    name: str
    version: SemVer
    files: dict[str, tuple[int, str]]

    @property
    def baseline_id(self) -> str:
        return f"{self.name}-{self.version}"


def manifest_document(files: dict[str, bytes]) -> bytes:
    """The canonical manifest for one bundle, so signing and checking agree."""
    if set(files) != set(BUNDLE_FILES):
        raise ValueError("a bundle manifest needs exactly the bundled files")
    baseline = parse_baseline(files[BASELINE], "bundle")
    if not baseline.is_official:
        raise ValueError("only the official baseline is released as a bundle")
    document = {
        "schema": MANIFEST_SCHEMA,
        "baseline_id": baseline.baseline_id,
        "files": {
            name: {
                "size": len(files[name]),
                "sha256": hashlib.sha256(files[name]).hexdigest(),
            }
            for name in sorted(BUNDLE_FILES)
        },
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def parse_manifest(content: bytes) -> Manifest:
    """Accept only the exact manifest shape; an unknown field is a refusal."""
    if not content or len(content) > MAX_MANIFEST_BYTES:
        raise ValueError("the manifest has an invalid size")
    document = json.loads(content.decode("utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "schema", "baseline_id", "files"
    }:
        raise ValueError("the manifest has an unexpected shape")
    if document["schema"] != MANIFEST_SCHEMA:
        raise ValueError("the manifest schema is not supported")
    baseline_id = document["baseline_id"]
    if not isinstance(baseline_id, str):
        raise ValueError("the manifest names no baseline")
    match = re.fullmatch(rf"(?P<name>[a-z][a-z0-9-]*)-(?P<version>{SEMVER_TEXT})", baseline_id)
    if match is None or match.group("name") != OFFICIAL_NAME:
        raise ValueError("the manifest names no official baseline")
    version = SemVer.parse(match.group("version"))
    if version.metadata:
        raise ValueError("the manifest names no official baseline")
    entries = document["files"]
    if not isinstance(entries, dict) or set(entries) != set(BUNDLE_FILES):
        raise ValueError("the manifest does not list exactly the bundled files")
    files: dict[str, tuple[int, str]] = {}
    for name, entry in entries.items():
        if not isinstance(entry, dict) or set(entry) != {"size", "sha256"}:
            raise ValueError(f"the manifest entry for {name} has an unexpected shape")
        size, digest = entry["size"], entry["sha256"]
        if isinstance(size, bool) or not isinstance(size, int):
            raise ValueError(f"the manifest entry for {name} has no valid size")
        if not 0 < size <= BUNDLE_FILES[name]:
            raise ValueError(f"the manifest entry for {name} exceeds its size limit")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"the manifest entry for {name} has no valid digest")
        files[name] = (size, digest)
    return Manifest(OFFICIAL_NAME, version, files)


def verify_manifest_signature(
    manifest: bytes,
    signature: bytes,
    allowed_signers: tuple[str, ...] | None = None,
) -> None:
    """Let OpenSSH check the signature against the release keys carried here."""
    if allowed_signers is None:
        allowed_signers = ALLOWED_SIGNERS
    if not allowed_signers:
        raise ValueError("this installer carries no release signing key")
    ssh_keygen = shutil.which("ssh-keygen")
    if ssh_keygen is None:
        raise ValueError("ssh-keygen (OpenSSH) is required to verify a signed bundle")
    if not manifest or len(manifest) > MAX_MANIFEST_BYTES:
        raise ValueError("the manifest has an invalid size")
    if (
        not signature.startswith(SIGNATURE_HEADER)
        or len(signature) > MAX_SIGNATURE_BYTES
    ):
        raise ValueError("the manifest signature has an unexpected format")
    with tempfile.TemporaryDirectory(prefix="aiscb-verify.") as directory:
        signers_path = Path(directory) / "allowed_signers"
        signature_path = Path(directory) / SIGNATURE_NAME
        signers_path.write_text("".join(f"{line}\n" for line in allowed_signers))
        signature_path.write_bytes(signature)
        completed = subprocess.run(
            [
                ssh_keygen, "-Y", "verify",
                "-f", str(signers_path),
                "-I", SIGNER_PRINCIPAL,
                "-n", SIGNATURE_NAMESPACE,
                "-s", str(signature_path),
            ],
            input=manifest,
            capture_output=True,
            timeout=SSH_KEYGEN_TIMEOUT,
            check=False,
        )
    if completed.returncode != 0:
        raise ValueError("the manifest signature is not from a trusted release key")


def fetch_verified_bundle(
    fetch_json: Callable[[str], object],
    tag: str,
    version: SemVer,
    verify: Callable[[bytes, bytes], None] = verify_manifest_signature,
) -> dict[str, bytes]:
    """Download one release bundle, accepting nothing the signed manifest does not pin."""
    manifest_content = fetch_release_file(
        fetch_json, MANIFEST_NAME, tag, MAX_MANIFEST_BYTES
    )
    signature = fetch_release_file(fetch_json, SIGNATURE_NAME, tag, MAX_SIGNATURE_BYTES)
    verify(manifest_content, signature)
    manifest = parse_manifest(manifest_content)
    if manifest.version != version:
        raise ValueError("the manifest does not describe the release it was fetched from")
    files: dict[str, bytes] = {}
    for name, (size, digest) in manifest.files.items():
        content = fetch_release_file(fetch_json, name, tag, size)
        if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f"release {name} does not match the signed manifest")
        files[name] = content
    baseline = parse_baseline(files[BASELINE], f"GitHub release {tag}")
    if baseline.baseline_id != manifest.baseline_id:
        raise ValueError("the release baseline and the signed manifest disagree")
    return files


def release_update(
    *,
    output: Callable[[str], None] = print,
    current: Baseline | None = None,
    fetch_json: Callable[[str], object] = _read_json_url,
    verify: Callable[[bytes, bytes], None] = verify_manifest_signature,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> int:
    """Fetch the signed release bundle and hand over to its own guided setup.

    Nothing downloaded is executed or written outside a temporary directory
    before the signature and every digest have been checked.
    """
    current = current or bundled_baseline()
    if not current.is_official:
        output(
            f"{current.baseline_id} is a derived baseline; its updates come from "
            "the organization that derived it."
        )
        return 2
    try:
        tag, version = fetch_release_tag(fetch_json)
    except urllib.error.HTTPError as error:
        output("No published release found." if error.code == 404
               else "The release lookup failed.")
        return 1
    except (OSError, ValueError, json.JSONDecodeError):
        output("The release lookup failed.")
        return 1
    if version <= current.version:
        output(f"{current.baseline_id} is current.")
        return 0
    output(f"Release {OFFICIAL_NAME}-{version} is published; verifying its bundle...")
    try:
        files = fetch_verified_bundle(fetch_json, tag, version, verify)
    except ValueError as error:
        output(f"Update refused: {error}.")
        output(f"Run the current Quick start instead: {QUICK_START_URL}")
        return 2
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError,
            subprocess.TimeoutExpired):
        output("The bundle download failed; nothing was changed.")
        return 1
    with tempfile.TemporaryDirectory(prefix="aiscb-update.") as directory:
        staged = Path(directory)
        for name, content in files.items():
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_new(target, content)
        output(f"Verified bundle {OFFICIAL_NAME}-{version}; starting its guided setup.\n")
        completed = run(
            [sys.executable, str(staged / "scripts" / INSTALLER_NAME),
             "--interactive", "--offline"],
            check=False,
        )
    return int(completed.returncode)


def _entry_digest(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    digest = entry.get("sha256")
    if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
        return digest
    return None


def _link_points_to(target: Path, source: Path) -> bool:
    return target.is_symlink() and target.resolve(strict=False) == source.resolve(
        strict=False
    )


def _import_contains(target: Path, source: Path) -> bool:
    if not target.is_file():
        return False
    try:
        return f"@{source}" in _instruction_lines(target)
    except (OSError, UnicodeDecodeError, ValueError):
        return False


def installed_tools(
    targets: dict[str, list[tuple[str, Path]]], source: Path
) -> tuple[str, ...]:
    found: list[str] = []
    for tool, actions in targets.items():
        if not actions:
            continue
        matches = []
        for kind, target in actions:
            if kind == "link":
                matches.append(_link_points_to(target, source) or _session_link(target, source))
            else:
                matches.append(_import_contains(target, source) or any(
                    _session_link(link, source) and _import_contains(target, link)
                    for action, link in actions if action == "link"
                ))
        if all(matches):
            found.append(tool)
    return tuple(found)


def scan_project(root: Path, entry: object = None) -> Installation | None:
    source = root / BASELINE
    if source.is_symlink() or not source.is_file():
        return None
    try:
        baseline = read_baseline(source)
    except (OSError, ValueError):
        return None
    tools = installed_tools(project_targets(root), source)
    if not tools and not isinstance(entry, dict):
        return None
    return Installation(
        "project", root, source, baseline, tools, _entry_digest(entry)
    )


def scan_unmanaged_project_files(root: Path) -> list[Installation]:
    installations: list[Installation] = []
    central = (root / BASELINE).resolve(strict=False)
    for tool, actions in project_targets(root).items():
        target = actions[0][1]
        if target.is_symlink() or not target.is_file():
            continue
        if target.resolve(strict=False) == central:
            continue
        try:
            baseline = read_baseline(target)
        except (OSError, ValueError):
            continue
        installations.append(
            Installation("unmanaged", root, target, baseline, (tool,))
        )
    return installations


def scan_user(home: Path, user_entry: object = None) -> list[Installation]:
    targets = user_targets(home)
    sources: dict[Path, set[str]] = {}

    claude_link = targets["claude"][0][1]
    if claude_link.is_symlink():
        source = _instruction_source(claude_link)
        if _import_contains(
            targets["claude"][1][1], source
        ) or _import_contains(targets["claude"][1][1], claude_link):
            sources.setdefault(source, set()).add("claude")

    for tool in ("codex", "copilot"):
        link = targets[tool][0][1]
        if link.is_symlink():
            source = _instruction_source(link)
            sources.setdefault(source, set()).add(tool)

    managed_path = user_source(home)
    managed = managed_path.resolve(strict=False)
    managed_is_regular = managed_path.is_file() and not managed_path.is_symlink()
    if isinstance(user_entry, dict) and managed not in sources and managed_is_regular:
        sources[managed] = set()

    installations: list[Installation] = []
    for source, tools in sources.items():
        if not source.is_file():
            continue
        try:
            baseline = read_baseline(source)
        except (OSError, ValueError):
            continue
        is_managed = managed_is_regular and source == managed
        installations.append(
            Installation(
                "user" if is_managed else "legacy-user",
                home,
                source,
                baseline,
                tuple(tool for tool in TOOLS if tool in tools),
                _entry_digest(user_entry) if is_managed else None,
            )
        )

    seen = {item.source.resolve(strict=False) for item in installations}
    claude_file = targets["claude"][0][1]
    if (
        claude_file.is_file()
        and not claude_file.is_symlink()
        and claude_file.resolve(strict=False) not in seen
        and _import_contains(targets["claude"][1][1], claude_file)
    ):
        try:
            baseline = read_baseline(claude_file)
        except (OSError, ValueError):
            pass
        else:
            installations.append(
                Installation("unmanaged", home, claude_file, baseline, ("claude",))
            )
            seen.add(claude_file.resolve(strict=False))

    for tool in ("codex", "copilot"):
        instruction_file = targets[tool][0][1]
        if (
            instruction_file.is_file()
            and not instruction_file.is_symlink()
            and instruction_file.resolve(strict=False) not in seen
        ):
            try:
                baseline = read_baseline(instruction_file)
            except (OSError, ValueError):
                continue
            installations.append(
                Installation("unmanaged", home, instruction_file, baseline, (tool,))
            )
            seen.add(instruction_file.resolve(strict=False))
    return installations


def discover_installations(
    home: Path,
    registry: dict[str, object],
    current_root: Path | None = None,
) -> list[Installation]:
    user_entry = registry.get("user")
    installations = scan_user(home, user_entry if isinstance(user_entry, dict) else {})
    projects = registry.get("projects", {})
    if not isinstance(projects, dict):
        return installations
    for value, entry in list(projects.items())[:MAX_PROJECTS]:
        if not isinstance(value, str) or len(value) > 4096:
            continue
        root = Path(value)
        if not root.is_absolute() or root == Path(root.anchor) or not root.is_dir():
            continue
        installation = scan_project(root, entry)
        if installation:
            installations.append(installation)
        installations.extend(scan_unmanaged_project_files(root))

    if current_root is not None:
        current_root = current_root.resolve()
        current_entry = projects.get(str(current_root))
        installation = scan_project(
            current_root,
            current_entry if isinstance(current_entry, dict) else {},
        )
        current_items = ([installation] if installation else [])
        current_items.extend(scan_unmanaged_project_files(current_root))
        seen = {
            item.source.resolve(strict=False)
            for item in installations
        }
        for item in current_items:
            source = item.source.resolve(strict=False)
            if source not in seen:
                installations.append(item)
                seen.add(source)
    return installations


def record_installation(
    registry: dict[str, object], installation: Installation, *, trusted: bool
) -> None:
    previous: object = None
    if installation.kind == "project":
        projects = registry.get("projects", {})
        if isinstance(projects, dict):
            previous = projects.get(str(installation.root.resolve()))
    elif installation.kind in {"user", "legacy-user"}:
        previous = registry.get("user")
    previous_tools = previous.get("tools", []) if isinstance(previous, dict) else []
    tools = [
        tool
        for tool in TOOLS
        if tool in installation.tools or tool in previous_tools
    ]
    entry = {
        "baseline_id": installation.baseline.baseline_id,
        "sha256": installation.baseline.digest if trusted else None,
        "tools": tools,
    }
    if installation.kind == "project":
        projects = registry.setdefault("projects", {})
        if isinstance(projects, dict):
            projects[str(installation.root.resolve())] = entry
    elif installation.kind in {"user", "legacy-user"}:
        registry["user"] = entry


def _remove_import_line(target: Path, source: Path, report: list[str]) -> None:
    """Take out the line that names our baseline, never the file around it."""
    if target.is_symlink() or not target.is_file():
        return
    try:
        content = read_limited(target, MAX_INSTRUCTION_BYTES).decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        report.append(f"blocked {target}: cannot safely read the instruction file")
        return
    line = f"@{source}"
    lines = content.splitlines()
    if line not in lines:
        return
    kept = [item for item in lines if item != line]
    if not any(item.strip() for item in kept):
        target.unlink()
        report.append(f"removed {target}")
        return
    trailing = "\n" if content.endswith("\n") else ""
    _atomic_replace(target, ("\n".join(kept) + trailing).encode())
    report.append(f"updated {target}: dropped the import line")


def _remove_merged_version_hook(
    path: Path, event: str, entry: dict[str, object], report: list[str]
) -> None:
    try:
        config, existed = _read_hook_config(path)
        if not existed:
            return
        hooks = config.get("hooks")
        entries = hooks.get(event) if isinstance(hooks, dict) else None
        if not isinstance(entries, list):
            return
        kept = [item for item in entries if not _is_moved_version_hook(item, entry)]
        if len(kept) == len(entries):
            return
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
            if not hooks:
                del config["hooks"]
        if config:
            _write_hook_config(path, config, True)
            report.append(f"updated {path}: dropped the startup hook")
        else:
            path.unlink()
            report.append(f"removed {path}")
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        report.append(f"blocked {path}: cannot safely remove the startup hook")


def _remove_copilot_version_hook(
    path: Path, config: dict[str, object], report: list[str]
) -> None:
    try:
        current, existed = _read_hook_config(path)
        if not existed:
            return
        if not _is_moved_version_hook(current, config):
            report.append(f"blocked {path}: contains a different hook configuration")
            return
        path.unlink()
        report.append(f"removed {path}")
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        report.append(f"blocked {path}: cannot safely remove the startup hook")


def _remove_version_hooks(root: Path, home: Path | None, report: list[str]) -> None:
    helper = version_hook_path(root, home)
    project = home is None
    for tool in TOOLS:
        if tool == "claude":
            path = (root / ".claude" / "settings.json") if project else (
                home / ".claude" / "settings.json"
            )
            _remove_merged_version_hook(
                path, "SessionStart", _claude_version_hook(helper, project), report
            )
        elif tool == "codex":
            path = (root / ".codex" / "hooks.json") if project else (
                home / ".codex" / "hooks.json"
            )
            _remove_merged_version_hook(
                path, "SessionStart", _codex_version_hook(helper, project), report
            )
        else:
            hook_root = root / ".github" / "hooks" if project else (
                home / ".copilot" / "hooks"
            )
            for name in (
                COPILOT_VERSION_HOOK_NAME,
                PREVIOUS_COPILOT_VERSION_HOOK_NAME,
            ):
                _remove_copilot_version_hook(
                    hook_root / name,
                    _copilot_version_config(helper, project),
                    report,
                )
    for tool in ("claude", "codex"):
        _remove_merged_version_hook(
            _session_hook_path(tool, root, home), "SessionStart",
            _session_hook(tool, helper, home is None), report,
        )
        _remove_merged_version_hook(
            _session_hook_path(tool, root, home), "UserPromptSubmit",
            _session_check_hook(tool, helper, home is None), report,
        )
    if helper.is_symlink() or not helper.is_file():
        return
    try:
        digest = hashlib.sha256(read_limited(helper, MAX_BASELINE_BYTES)).hexdigest()
    except (OSError, ValueError):
        report.append(f"blocked {helper}: cannot safely read the hook helper")
        return
    if digest not in KNOWN_HOOK_DIGESTS:
        report.append(f"blocked {helper}: contains different hook helper code")
        return
    helper.unlink()
    report.append(f"removed {helper}")


def _managed_source(installation: Installation) -> bool:
    """Whether the baseline file itself was placed here by this installer."""
    if installation.kind == "user":
        return installation.source.resolve(strict=False) == user_source(
            installation.root
        ).resolve(strict=False)
    if installation.kind == "project":
        return installation.source.resolve(strict=False) == (
            installation.root / BASELINE
        ).resolve(strict=False)
    return False


def remove_installation(installation: Installation, report: list[str]) -> bool:
    """Take back what this installer put in place, and nothing else."""
    if installation.kind == "unmanaged":
        report.append(
            f"skipped {installation.label}: this file was not placed by the installer"
        )
        return False
    project = installation.kind == "project"
    root = installation.root
    home = None if project else installation.root
    targets = project_targets(root) if project else user_targets(root)
    session_claude = _session_link(targets["claude"][0][1], installation.source)
    for actions in targets.values():
        for kind, target in actions:
            if kind == "link":
                if _link_points_to(target, installation.source) or _session_link(target, installation.source):
                    target.unlink()
                    report.append(f"removed {target}")
            else:
                _remove_import_line(target, installation.source, report)
    if not project and session_claude:
        _remove_import_line(targets["claude"][1][1], targets["claude"][0][1], report)
    helper = version_hook_path(root, home)
    loader = helper.parent / SESSION_LOADER_NAME
    if loader.is_file() and not loader.is_symlink():
        if read_limited(loader, MAX_INSTRUCTION_BYTES) == _session_loader(installation.source, helper):
            loader.unlink()
            report.append(f"removed {loader}")
    _remove_version_hooks(root, home, report)
    if _managed_source(installation):
        installation.source.unlink()
        report.append(f"removed {installation.source}")
    if not project:
        data = user_data_root(root)
        installer = data / INSTALLER_NAME
        if installer.is_file() and not installer.is_symlink():
            installer.unlink()
            report.append(f"removed {installer}")
        if data.is_dir() and not any(data.iterdir()):
            data.rmdir()
    else:
        hook_dir = root / VERSION_HOOK_DIR
        if hook_dir.is_dir() and not any(hook_dir.iterdir()):
            hook_dir.rmdir()
    return True


def forget_installation(
    registry: dict[str, object], installation: Installation
) -> None:
    if installation.kind == "project":
        projects = registry.get("projects")
        if isinstance(projects, dict):
            projects.pop(str(installation.root.resolve()), None)
    elif installation.kind in {"user", "legacy-user"}:
        registry["user"] = None


def _backup_path(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.bak")
    for number in range(1, 101):
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        candidate = path.with_name(f"{path.name}.bak.{number}")
    raise ValueError("too many backup files")


def _atomic_symlink(target: Path, source: Path) -> None:
    temporary = target.with_name(f".{target.name}.aiscb-{secrets.token_hex(8)}")
    try:
        temporary.symlink_to(str(source))
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_import(target: Path, old_source: Path, new_source: Path) -> bool:
    if target.is_symlink() or not target.is_file():
        return False
    try:
        content = read_limited(target, MAX_INSTRUCTION_BYTES).decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    old_line, new_line = f"@{old_source}", f"@{new_source}"
    lines = content.splitlines()
    if new_line in lines:
        return True
    if old_line not in lines:
        return False
    replaced = [new_line if line == old_line else line for line in lines]
    trailing = "\n" if content.endswith("\n") else ""
    _atomic_replace(target, ("\n".join(replaced) + trailing).encode())
    return True


def migrate_legacy_user(
    installation: Installation, available: Baseline
) -> tuple[list[str], Installation | None]:
    report: list[str] = []
    home = installation.root
    destination = user_source(home)
    if destination.is_symlink():
        return [f"blocked {destination}: is a symlink"], None
    if destination.exists():
        try:
            existing = read_baseline(destination)
        except (OSError, ValueError):
            return [f"blocked {destination}: is not a valid baseline"], None
        if existing.digest != available.digest:
            return [f"blocked {destination}: contains a different baseline"], None
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _write_new(destination, available.content)
        report.append(f"added {destination}")

    targets = user_targets(home)
    claude_link = targets["claude"][0][1]
    migrated: list[str] = []
    for tool in installation.tools:
        complete = True
        for kind, target in targets[tool]:
            if kind == "link":
                complete = complete and (
                    _link_points_to(target, destination)
                    or _link_points_to(target, installation.source)
                )
            else:
                complete = complete and not target.is_symlink() and (
                    _import_contains(target, destination)
                    or _import_contains(target, installation.source)
                    or (tool == "claude" and _import_contains(target, claude_link))
                )
        if not complete:
            report.append(f"blocked {TOOL_LABELS[tool]}: changed since discovery")
            continue
        for kind, target in targets[tool]:
            if kind == "link":
                if _link_points_to(target, destination):
                    continue
                _atomic_symlink(target, destination)
                report.append(f"linked {target} -> {destination}")
            elif tool == "claude" and _import_contains(target, claude_link):
                continue
            elif not _replace_import(target, installation.source, destination):
                report.append(f"blocked {target}: import changed since discovery")
                complete = False
        if complete:
            migrated.append(tool)

    if not migrated:
        return report, None
    baseline = read_baseline(destination)
    result = Installation(
        "user", home, destination, baseline, tuple(migrated), baseline.digest
    )
    return report, result


def _lacks_install_record(installation: Installation) -> bool:
    """True when no registry entry vouches for the file, so it is backed up first."""
    return (
        installation.kind in {"project", "user"}
        and installation.tracked_digest != installation.baseline.digest
    )


def update_installation(
    installation: Installation,
    available: Baseline,
    replace_unrecorded: bool,
) -> tuple[list[str], Installation | None]:
    """Replace the installed baseline; a file without an install record needs consent.

    The caller asks that question, so the guided setup puts one prompt per
    installation to the user instead of a second one after the first yes.
    """
    if not installation.baseline.is_official:
        return [f"skipped {installation.label}: customized baseline"], None
    if installation.kind == "legacy-user":
        return migrate_legacy_user(installation, available)
    if installation.kind not in {"project", "user"}:
        return [f"skipped {installation.label}: not managed by this installer"], None
    if installation.source.is_symlink() or not installation.source.is_file():
        return [f"blocked {installation.source}: source is not a regular file"], None
    try:
        current = read_baseline(installation.source)
    except (OSError, ValueError):
        return [f"blocked {installation.source}: source changed since discovery"], None
    if current.digest != installation.baseline.digest:
        return [f"blocked {installation.source}: source changed since discovery"], None

    report: list[str] = []
    if _lacks_install_record(installation):
        if not replace_unrecorded:
            return [f"skipped {installation.label}: kept local content"], None
        backup = _backup_path(installation.source)
        _write_new(backup, installation.baseline.content)
        report.append(f"backed up {installation.source} to {backup}")

    _atomic_replace(installation.source, available.content)
    if installation.baseline.version == available.version:
        report.append(
            f"replaced differing {installation.baseline.baseline_id} content "
            f"in {installation.source}"
        )
    else:
        report.append(
            f"updated {installation.source}: "
            f"{installation.baseline.version} -> {available.version}"
        )
    baseline = read_baseline(installation.source)
    return report, Installation(
        installation.kind,
        installation.root,
        installation.source,
        baseline,
        installation.tools,
        baseline.digest,
    )


def _refresh_updated_artifacts(
    installation: Installation, report: list[str]
) -> bool:
    """Refresh the bundled installer/helper that belong to an updated scope.

    User installations always carry both files. Project installations carry
    only the helper, and only after a startup hook or session switch placed it.
    Return whether a bundled artifact could not be refreshed.
    """
    incomplete = False
    if installation.kind in {"user", "legacy-user"}:
        if _place_installer(installation.root, report) is None:
            incomplete = True
        if _place_version_hook(
            installation.root, installation.root, report
        ) is None:
            incomplete = True
    elif installation.kind == "project":
        helper = version_hook_path(installation.root, None)
        if (helper.exists() or helper.is_symlink()) and _place_version_hook(
            installation.root, None, report
        ) is None:
            incomplete = True
    return incomplete


def _read_answer(input_fn: Callable[[str], str], prompt: str) -> str:
    answer = input_fn(prompt)
    if len(answer) > 4096:
        raise ValueError("input is too long")
    return answer.strip()


def ask_yes_no(
    input_fn: Callable[[str], str],
    question: str,
    default: bool,
    output: Callable[[str], None] = print,
) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    for _ in range(3):
        answer = _read_answer(input_fn, question + suffix).lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        output("Please answer yes or no.")
    return default


def choose_tools(
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
    tools: tuple[str, ...],
    default_tools: list[str] | None = None,
    heading: str = "Install for which tools?",
) -> list[str] | None:
    defaults = (
        [tool for tool in default_tools if tool in tools]
        if default_tools is not None
        else list(tools)
    )
    has_installed_tools = default_tools is not None and bool(defaults)
    if not defaults:
        defaults = list(tools)
    if has_installed_tools:
        default_label = "keep installed (" + ", ".join(
            TOOL_LABELS[tool] for tool in defaults
        ) + "); all = all"
    else:
        default_label = "both" if len(tools) == 2 else "all"
    output(f"\n{heading}")
    for number, tool in enumerate(tools, 1):
        installed = (
            " (installed)" if has_installed_tools and tool in defaults else ""
        )
        output(f"  {number}. {TOOL_LABELS[tool]}{installed}")
    for _ in range(3):
        answer = _read_answer(
            input_fn,
            f"Tools (comma-separated; Enter = {default_label}): ",
        )
        if not answer:
            return defaults
        if answer.lower() == "all":
            return list(tools)
        chosen: list[str] = []
        valid = True
        for item in re.split(r"[\s,]+", answer.lower()):
            if item.isdigit() and 1 <= int(item) <= len(tools):
                tool = tools[int(item) - 1]
            elif item in tools:
                tool = item
            else:
                valid = False
                break
            if tool not in chosen:
                chosen.append(tool)
        if valid and chosen:
            return chosen
        output("Invalid selection. Use numbers or tool names separated by commas.")
    return None


def _path_from_answer(answer: str, home: Path) -> Path:
    if answer == "~":
        candidate = home
    elif answer.startswith("~/"):
        candidate = home / answer[2:]
    else:
        candidate = Path(answer)
    return candidate.resolve()


def _detect_project_root(location: Path) -> Path | None:
    for candidate in (location, *location.parents):
        git_marker = candidate / ".git"
        if git_marker.is_file() or (
            git_marker.is_dir() and (git_marker / "HEAD").is_file()
        ):
            return candidate
        if candidate == location and scan_project(candidate, {}) is not None:
            return candidate
    return None


def _is_previous_managed_user(installation: Installation) -> bool:
    previous = previous_user_data_root(installation.root)
    return (
        installation.kind == "legacy-user"
        and installation.source.parent.resolve(strict=False)
        == previous.resolve(strict=False)
    )


def _join_words(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + f" and {words[-1]}"


def _join_labels(tools: list[str] | tuple[str, ...]) -> str:
    return _join_words([TOOL_LABELS[tool] for tool in tools])


def _sentence(text: str) -> str:
    """Capitalize only the first letter, so a quoted path keeps its case."""
    return text[:1].upper() + text[1:]


def _scope_name(installation: Installation) -> str:
    if installation.kind == "project":
        return f"project {display_path(installation.root)}"
    if installation.kind == "legacy-user":
        return f"your user account (linked to {display_path(installation.source)})"
    return "your user account"


def _scope_names(installations: list[Installation]) -> str:
    return _join_words([_scope_name(item) for item in installations])


def _latest_known(registry: dict[str, object]) -> tuple[str, str] | None:
    """The release an earlier check recorded, with the day it was checked."""
    section = registry.get(UPDATE_CHECK_KEY)
    if not isinstance(section, dict):
        return None
    latest, checked = section.get("latest"), section.get("checked")
    if not isinstance(latest, str) or isinstance(checked, bool):
        return None
    if not isinstance(checked, int) or checked < 0:
        return None
    try:
        return latest, time.strftime("%Y-%m-%d", time.gmtime(checked))
    except (OverflowError, OSError, ValueError):
        return None


def _version_phrase(
    installation: Installation,
    available: Baseline,
    released: Baseline | None,
    latest_known: tuple[str, str] | None,
) -> str:
    """Say how current an installation is, never more than this run knows.

    Only a release check in this run supports a plain "up to date"; otherwise
    the phrase names the last recorded check and its day, or that none ran.
    A file no tool loads gets no up-to-date claim, but keeps a pending update
    visible because the menu still offers it.
    """
    identifier = installation.baseline.baseline_id
    older = installation.baseline.version < available.version
    if installation.kind == "legacy-user" and not (
        installation.has_update(available) and older
    ):
        return f"{identifier}, switch to a managed copy so updates reach it"
    if not installation.baseline.is_official:
        if installation.baseline.name != OFFICIAL_NAME:
            return f"{identifier}, setup leaves it unchanged"
        return f"{identifier}, customized, setup leaves it unchanged"
    if installation.kind == "unmanaged":
        return f"{identifier}, setup leaves it unchanged"
    if installation.has_update(available):
        if older:
            phrase = f"{identifier}, update to {available.baseline_id} available"
        else:
            phrase = f"{identifier}, differs from {available.baseline_id}"
        if _lacks_install_record(installation):
            phrase += ", needs confirmation and backup"
        return phrase
    if installation.baseline.version > available.version:
        return f"{identifier}, newer than {available.baseline_id}"
    if not installation.tools:
        return identifier
    if released is not None:
        return f"{identifier}, up to date"
    unknown = f"{identifier}, newest release not checked"
    if latest_known is None:
        return unknown
    latest, checked_on = latest_known
    match = re.fullmatch(
        rf"(?P<name>[a-z][a-z0-9-]*)-(?P<version>{SEMVER_TEXT})", latest
    )
    if match is None or match.group("name") != installation.baseline.name:
        return unknown
    try:
        newer = SemVer.parse(match.group("version")) > installation.baseline.version
    except ValueError:
        return unknown
    if newer:
        return f"{identifier}, update to {latest} available (checked {checked_on})"
    return f"{identifier}, up to date as of {checked_on}"


def _session_notice_tools(installation: Installation) -> list[str]:
    """The tools of a managed installation whose session notice is configured."""
    if installation.kind not in {"user", "project"}:
        return []
    home = None if installation.kind == "project" else installation.root
    return [
        tool
        for tool in installation.tools
        if _version_hook_is_installed(tool, installation.root, home)
    ]


def _scope_title(installation: Installation, home: Path) -> str:
    source = display_path(installation.source)
    if installation.kind == "user":
        return "Your user account (all projects)"
    if installation.kind == "legacy-user":
        return f"Your user account (all projects), linked to {source}"
    if installation.kind == "project":
        return f"Project {display_path(installation.root)}"
    if installation.root.resolve(strict=False) == home.resolve(strict=False):
        return f"Your user account: manual file {source}"
    return f"Project {display_path(installation.root)}: manual file {source}"


def _release_line(
    available: Baseline, released: Baseline | None, check_online: bool
) -> str | None:
    """Name the newest release only as far as this run actually checked it."""
    if released is not None:
        if available is released:
            return f"Newest release: {released.baseline_id} (checked online just now)"
        return (
            f"Newest release: {released.baseline_id}; "
            f"this copy has the newer {available.baseline_id}"
        )
    if check_online:
        return (
            "Newest release: could not be checked; "
            f"this copy has {available.baseline_id}"
        )
    if LOCAL_ORIGIN == "installed copy":
        return None
    return f"Online check skipped; this copy has {available.baseline_id}"


def _show_setup_status(
    output: Callable[[str], None],
    installations: list[Installation],
    available: Baseline,
    home: Path,
    current_root: Path | None,
    registry: dict[str, object],
    released: Baseline | None,
) -> None:
    current_resolved = (
        current_root.resolve(strict=False) if current_root is not None else None
    )
    home_resolved = home.resolve(strict=False)
    current: list[Installation] = []
    user: list[Installation] = []
    other: list[Installation] = []
    for installation in installations:
        root = installation.root.resolve(strict=False)
        if installation.kind in {"user", "legacy-user"}:
            user.append(installation)
        elif installation.kind == "unmanaged" and root == home_resolved:
            user.append(installation)
        elif current_resolved is not None and root == current_resolved:
            current.append(installation)
        else:
            other.append(installation)

    latest_known = None if released is not None else _latest_known(registry)

    def show(installation: Installation) -> None:
        output(f"\n{_scope_title(installation, home)}")
        phrase = _version_phrase(installation, available, released, latest_known)
        output(f"  {phrase}")
        if not installation.tools:
            output("  Not loaded by any tool")
            return
        output(f"  Loaded by {_join_labels(installation.tools)}")
        if installation.kind not in {"user", "project"}:
            return
        notice = _session_notice_tools(installation)
        if not notice:
            output("  Session notice: off")
        elif len(notice) == len(installation.tools):
            output("  Session notice: on")
        else:
            output(f"  Session notice: on for {_join_labels(notice)}")

    if not any(item.kind in {"user", "legacy-user"} for item in user):
        output("\nYour user account: not installed")
    for installation in user:
        show(installation)
    if current_root is not None and not any(
        item.kind == "project" for item in current
    ):
        output(f"\nProject {display_path(current_root)}: not installed")
    for installation in current + other:
        show(installation)

    notes: list[str] = []
    if any(_session_notice_tools(item) for item in installations):
        notes.append(
            "Update notice: on" if update_check_enabled(registry)
            else "Update notice: off, so you won't hear about new versions"
        )
    if LOCAL_ORIGIN == "installed copy":
        notes.append(
            "Check for a new version: "
            f"python3 {display_path(INSTALLER_SOURCE)} --update"
        )
    if notes:
        output("")
        for line in notes:
            output(line)


def _record_current_scope(
    registry: dict[str, object],
    installation: Installation | None,
    available: Baseline,
) -> None:
    if not installation:
        return
    trusted = (
        installation.baseline.digest == available.digest
        or installation.tracked_digest == installation.baseline.digest
    )
    record_installation(registry, installation, trusted=trusted)


def _update_key(installation: Installation) -> Path:
    return installation.source.resolve(strict=False)


def _outdated_installations(
    installations: list[Installation],
    available: Baseline,
    reviewed: set[Path],
) -> list[Installation]:
    return [
        item
        for item in installations
        if item.has_update(available) and _update_key(item) not in reviewed
    ]


def _apply_update(
    installation: Installation,
    available: Baseline,
    registry: dict[str, object],
    output: Callable[[str], None],
) -> tuple[bool, bool]:
    report: list[str] = []
    artifact_incomplete = _refresh_updated_artifacts(installation, report)
    artifact_changed = any(
        line.startswith(("added ", "updated ")) for line in report
    )
    if artifact_incomplete:
        for line in report:
            output(f"  {line}")
        return artifact_changed, True

    update_report, updated = update_installation(
        installation, available, replace_unrecorded=True
    )
    report.extend(update_report)
    if updated:
        record_installation(registry, updated, trusted=True)
    for line in report:
        output(f"  {line}")
    incomplete = updated is None and any(
        line.startswith("blocked") for line in report
    )
    return artifact_changed or updated is not None, incomplete


def _review_updates(
    installations: list[Installation],
    available: Baseline,
    registry: dict[str, object],
    reviewed: set[Path],
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
) -> tuple[bool, bool]:
    outdated = _outdated_installations(installations, available, reviewed)
    if not outdated:
        return False, False

    changed = False
    incomplete = False
    for installation in outdated:
        reviewed.add(_update_key(installation))
        if installation.baseline.version < available.version:
            question = (
                f"\nUpdate {installation.label} "
                f"{installation.baseline.baseline_id} → {available.baseline_id}?"
            )
        else:
            question = (
                f"\nReplace the differing {installation.baseline.baseline_id} content "
                f"in {installation.label} with the available copy?"
            )
        unrecorded = _lacks_install_record(installation)
        if unrecorded:
            question += " No install record for this file, so it is backed up first."
        if not ask_yes_no(input_fn, question, not unrecorded, output):
            output(f"  kept {installation.label} unchanged")
            continue
        update_changed, update_incomplete = _apply_update(
            installation, available, registry, output
        )
        changed = changed or update_changed
        incomplete = incomplete or update_incomplete
    return changed, incomplete


def _choose_scopes(
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
    installations: list[Installation],
    heading: str,
    *,
    enter_all: bool,
) -> list[Installation]:
    """Pick one shown scope or all of them; Enter picks all or cancels."""
    everything = "both" if len(installations) == 2 else "all of them"
    last = len(installations) + 1
    output(f"\n{heading}")
    for number, item in enumerate(installations, 1):
        output(f"  {number}. {_scope_name(item)}")
    output(f"  {last}. {everything}")
    prompt = f"Choice [{last}]: " if enter_all else "Choice (Enter = cancel): "
    for _ in range(3):
        answer = _read_answer(input_fn, prompt)
        if not answer:
            return list(installations) if enter_all else []
        if answer.isdigit() and 1 <= int(answer) <= last:
            if int(answer) == last:
                return list(installations)
            return [installations[int(answer) - 1]]
        output(f"Invalid selection. Choose a number from 1 to {last}.")
    return []


def _update_interactively(
    outdated: list[Installation],
    available: Baseline,
    registry: dict[str, object],
    reviewed: set[Path],
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
) -> tuple[bool, bool, str | None]:
    """Update the shown scopes the user picks, preserving local-content consent."""
    chosen = (
        outdated
        if len(outdated) == 1
        else _choose_scopes(input_fn, output, outdated, "Update:", enter_all=True)
    )
    if not chosen:
        output("Nothing updated.")
        return False, False, None

    changed = False
    incomplete = False
    updated: list[Installation] = []
    for installation in chosen:
        reviewed.add(_update_key(installation))
        if _lacks_install_record(installation):
            question = (
                f"\n{_sentence(_scope_name(installation))} has no matching install "
                "record. Back it up and replace it?"
            )
            if not ask_yes_no(input_fn, question, False, output):
                output(f"  kept {_scope_name(installation)} unchanged")
                continue
        update_changed, update_incomplete = _apply_update(
            installation, available, registry, output
        )
        changed = changed or update_changed
        incomplete = incomplete or update_incomplete
        if update_changed and not update_incomplete:
            updated.append(installation)
    if not updated:
        return changed, incomplete, None
    verb = "uses" if len(updated) == 1 else "use"
    message = f"{_sentence(_scope_names(updated))} now {verb} {available.baseline_id}."
    return changed, incomplete, message


def _offer_session_notice(
    installation: Installation | None,
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
) -> tuple[bool, bool]:
    """Offer the session notice to every tool that lacks it; report the result."""
    if installation is None:
        return False, False
    configured_tools = _session_notice_tools(installation)
    tools = [tool for tool in installation.tools if tool not in configured_tools]
    if not tools:
        return False, False
    verb = "shows" if len(tools) == 1 else "show"
    output(f"\nSession notice: when a session starts, {_join_labels(tools)} {verb}")
    output(f"  AI Secure Coding Baseline active: {installation.baseline.baseline_id}")
    if "codex" in tools:
        output("Codex asks you once to approve it with /hooks.")
    if not ask_yes_no(input_fn, "Enable session notice?", True, output):
        return False, False
    home = None if installation.kind == "project" else installation.root
    for line in install_version_hooks(tools, installation.root, home):
        output(f"  {line}")
    output("\nVerifying session notice:")
    incomplete = False
    configured = False
    for tool in tools:
        if _version_hook_is_installed(tool, installation.root, home):
            output(f"  ✓ {TOOL_LABELS[tool]} session notice configured")
            configured = True
        else:
            output(f"  ! {TOOL_LABELS[tool]} session notice incomplete")
            incomplete = True
    return incomplete, configured


def _set_update_notice(registry: dict[str, object], enabled: bool) -> None:
    section = registry.get(UPDATE_CHECK_KEY)
    section = section if isinstance(section, dict) else {}
    registry[UPDATE_CHECK_KEY] = {**section, "enabled": enabled}


def _offer_update_notice(
    registry: dict[str, object],
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
) -> bool:
    """Ask whether the session notice may look up new releases in the background."""
    output("\nThe session notice will also say when a new version is out.")
    output("To find out, a background process asks api.github.com once a day.")
    output("It only reports; you still update with --update.")
    enabled = ask_yes_no(input_fn, "Enable update notice?", False, output)
    if enabled:
        _set_update_notice(registry, True)
    return enabled


def _remove_interactively(
    registry: dict[str, object],
    installations: list[Installation],
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
) -> list[Installation]:
    """Remove the scopes the user picks after one confirmation naming what goes."""
    chosen = (
        list(installations)
        if len(installations) == 1
        else _choose_scopes(
            input_fn, output, installations, "Remove from:", enter_all=False
        )
    )
    if not chosen:
        output("Nothing removed.")
        return []

    for item in chosen:
        output(f"\nThis removes from {_scope_name(item)}:")
        if item.tools:
            output(f"  the baseline for {_join_labels(item.tools)}")
        else:
            output("  the baseline")
        if _session_notice_tools(item):
            output("  the session notice")
        installer = user_data_root(item.root) / INSTALLER_NAME
        if item.kind != "project" and installer.is_file() and not installer.is_symlink():
            output(f"  this installer in {display_path(installer.parent)}")
    output("Projects not listed here keep their own installation.")
    if any(item.kind != "project" for item in chosen):
        output("To install again later, use the Quick start.")
    if not ask_yes_no(input_fn, "Remove?", False, output):
        output("Nothing removed.")
        return []

    removed: list[Installation] = []
    for item in chosen:
        report: list[str] = []
        if remove_installation(item, report):
            forget_installation(registry, item)
            removed.append(item)
        for line in report:
            output(f"  {line}")
    return removed


def _verify_baseline_tools(
    selected_tools: list[str],
    installed: Installation | None,
    output: Callable[[str], None],
) -> bool:
    configured = set(installed.tools) if installed is not None else set()
    output("\nVerifying baseline setup:")
    incomplete = False
    for tool in selected_tools:
        if tool in configured:
            output(f"  ✓ {TOOL_LABELS[tool]} configured")
        else:
            output(f"  ! {TOOL_LABELS[tool]} incomplete")
            incomplete = True
    return incomplete


def _add_label(missing: list[str], where: str) -> str:
    if len(missing) == 1:
        return f"add to {TOOL_LABELS[missing[0]]}{where}"
    labels = ", ".join(TOOL_LABELS[tool] for tool in missing)
    return f"add to more tools{where} ({labels})..."


def _rescan(
    installation: Installation, registry: dict[str, object]
) -> Installation | None:
    if installation.kind == "project":
        projects = registry.get("projects", {})
        entry = (
            projects.get(str(installation.root.resolve()))
            if isinstance(projects, dict)
            else None
        )
        return scan_project(installation.root, entry if isinstance(entry, dict) else {})
    user_entry = registry.get("user")
    managed = [
        item
        for item in scan_user(
            installation.root, user_entry if isinstance(user_entry, dict) else {}
        )
        if item.kind == "user"
    ]
    return managed[0] if managed else None


def _add_tools_interactively(
    installation: Installation,
    missing: list[str],
    available: Baseline,
    registry: dict[str, object],
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
) -> tuple[bool, bool, str | None]:
    """Link more tools to an installation; they inherit its session notice."""
    tools: list[str] | None = list(missing)
    if len(missing) > 1:
        tools = choose_tools(
            input_fn, output, tuple(missing), heading="Add the baseline to:"
        )
    if not tools:
        output("Setup cancelled.")
        return False, False, None
    project = installation.kind == "project"
    root = installation.root
    home = None if project else root
    output("\nApplying project setup:" if project else "\nApplying user-wide setup:")
    report = install(
        tools, root if project else Path.cwd(), home, content=available.content
    )
    for line in report:
        output(f"  {line}")
    installed = _rescan(installation, registry)
    _record_current_scope(registry, installed, available)
    incomplete = _verify_baseline_tools(tools, installed, output)
    added = [tool for tool in tools if installed is not None and tool in installed.tools]
    if added and _session_notice_tools(installation):
        output("\nAdding the session notice, as for the other tools:")
        for line in install_version_hooks(added, root, home):
            output(f"  {line}")
        for tool in added:
            if _version_hook_is_installed(tool, root, home):
                output(f"  ✓ {TOOL_LABELS[tool]} session notice configured")
            else:
                output(f"  ! {TOOL_LABELS[tool]} session notice incomplete")
                incomplete = True
        if "codex" in added:
            output("Codex asks you once to approve it with /hooks.")
    if installed is None or not added:
        return installed is not None, incomplete, None
    verb = "loads" if len(added) == 1 else "load"
    message = f"{_join_labels(added)} now {verb} {installed.baseline.baseline_id}."
    return True, incomplete, message


def _install_project_interactively(
    home: Path,
    registry: dict[str, object],
    available: Baseline,
    reviewed_updates: set[Path],
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
    root: Path | None = None,
) -> tuple[bool, bool]:
    if root is None:
        answer = _read_answer(input_fn, "Project directory (blank to cancel): ")
        if not answer:
            return False, False
        try:
            root = _path_from_answer(answer, home)
        except (OSError, RuntimeError):
            output("Invalid project path.")
            return False, False
    else:
        root = root.resolve()
    if root == Path(root.anchor) or not root.is_dir():
        output("Project directory must be an existing non-root directory.")
        return False, False

    projects = registry.get("projects", {})
    entry = projects.get(str(root)) if isinstance(projects, dict) else None
    existing = scan_project(root, entry if isinstance(entry, dict) else {})
    unmanaged = scan_unmanaged_project_files(root)
    found = ([existing] if existing else []) + unmanaged
    changed, update_incomplete = _review_updates(
        found,
        available,
        registry,
        reviewed_updates,
        input_fn,
        output,
    )

    default_tools = list(existing.tools) if existing and existing.tools else None
    tools = choose_tools(input_fn, output, TOOLS, default_tools)
    if not tools:
        output("Setup cancelled.")
        return changed, update_incomplete
    output("\nApplying project setup:")
    report = install(tools, root, None, content=available.content)
    for line in report:
        output(f"  {line}")
    projects = registry.get("projects", {})
    entry = projects.get(str(root)) if isinstance(projects, dict) else None
    installed = scan_project(root, entry if isinstance(entry, dict) else {})
    _record_current_scope(registry, installed, available)
    incomplete = _verify_baseline_tools(tools, installed, output)
    hook_incomplete, hooks_configured = _offer_session_notice(
        installed, input_fn, output
    )
    if hooks_configured and not update_check_enabled(registry):
        _offer_update_notice(registry, input_fn, output)
    return (
        changed or installed is not None,
        update_incomplete or incomplete or hook_incomplete,
    )


def _install_user_interactively(
    home: Path,
    registry: dict[str, object],
    available: Baseline,
    reviewed_updates: set[Path],
    input_fn: Callable[[str], str],
    output: Callable[[str], None],
) -> tuple[bool, bool]:
    user_entry = registry.get("user")
    existing = scan_user(home, user_entry if isinstance(user_entry, dict) else {})
    changed, update_incomplete = _review_updates(
        existing,
        available,
        registry,
        reviewed_updates,
        input_fn,
        output,
    )
    user_entry = registry.get("user")
    existing = scan_user(home, user_entry if isinstance(user_entry, dict) else {})
    legacy = [
        item
        for item in existing
        if item.kind == "legacy-user" and _update_key(item) not in reviewed_updates
    ]
    previous_managed = [
        installation
        for installation in legacy
        if _is_previous_managed_user(installation)
    ]
    migration_targets = previous_managed or legacy
    if migration_targets:
        legacy_tools = [
            tool
            for tool in TOOLS
            if any(tool in installation.tools for installation in migration_targets)
        ]
        legacy_labels = [TOOL_LABELS[tool] for tool in legacy_tools]
        if len(legacy_labels) > 1:
            legacy_subject = (
                ", ".join(legacy_labels[:-1]) + f" and {legacy_labels[-1]}"
            )
            legacy_verb = "read"
        else:
            legacy_subject = legacy_labels[0] if legacy_labels else "This installation"
            legacy_verb = "reads"
    if previous_managed:
        output(
            f"\n{legacy_subject} {legacy_verb} the baseline from the previous "
            "managed location:"
        )
        for installation in migration_targets:
            output(f"  {display_path(installation.source)}")
    elif migration_targets:
        output(
            f"\n{legacy_subject} {legacy_verb} the baseline from a file this setup "
            "does not manage:"
        )
        for installation in migration_targets:
            output(f"  {display_path(installation.source)}")
    migration_question = (
        f"Switch to a managed copy of {available.baseline_id}, so updates reach it?"
    )
    if migration_targets and ask_yes_no(input_fn, migration_question, True, output):
        for installation in migration_targets:
            reviewed_updates.add(_update_key(installation))
            report, migrated = migrate_legacy_user(installation, available)
            for line in report:
                output(line)
            if migrated:
                record_installation(registry, migrated, trusted=True)
                changed = True

    default_tools: list[str] = []
    for installation in existing:
        if installation.kind not in {"user", "legacy-user"}:
            continue
        for tool in installation.tools:
            if tool not in default_tools:
                default_tools.append(tool)
    tools = choose_tools(input_fn, output, TOOLS, default_tools or None)
    if not tools:
        output("Setup cancelled.")
        return changed, update_incomplete
    output("\nApplying user-wide setup:")
    report = install(tools, Path.cwd(), home, content=available.content)
    for line in report:
        output(f"  {line}")
    user_entry = registry.get("user")
    managed = [
        item
        for item in scan_user(
            home, user_entry if isinstance(user_entry, dict) else {}
        )
        if item.kind == "user"
    ]
    if managed:
        _record_current_scope(registry, managed[0], available)
        incomplete = _verify_baseline_tools(tools, managed[0], output)
        hook_incomplete, hooks_configured = _offer_session_notice(
            managed[0], input_fn, output
        )
        if hooks_configured and not update_check_enabled(registry):
            _offer_update_notice(registry, input_fn, output)
        return True, update_incomplete or incomplete or hook_incomplete
    _verify_baseline_tools(tools, None, output)
    return changed, True


def _save_setup_registry(
    state_path: Path,
    registry: dict[str, object],
    registry_writable: bool,
    output: Callable[[str], None],
) -> None:
    if registry_writable:
        save_registry(state_path, registry)
    else:
        output("Changes completed, but the invalid registry was not overwritten.")


def interactive_setup(
    *,
    home: Path,
    input_fn: Callable[[str], str] = input,
    output: Callable[[str], None] = print,
    check_online: bool = True,
    state_path: Path | None = None,
    current_root: Path | None = None,
) -> int:
    output("AI Secure Coding Baseline setup")
    if check_online:
        output("Checking for the newest release...")
    available, _note, released = latest_available(check_online)
    state_path = state_path or registry_path(home)
    registry, registry_writable, registry_note = load_registry_with_previous(
        home, state_path
    )
    if registry_writable:
        cache_release_check(state_path, registry, released)
    explicit_project = current_root is not None
    location = (current_root or Path.cwd()).resolve()
    if not location.is_dir():
        raise ValueError("current location must be an existing directory")
    project_root = location if explicit_project else _detect_project_root(location)
    if project_root is not None and project_root == Path(project_root.anchor):
        project_root = None

    release_line = _release_line(available, released, check_online)
    if release_line:
        output(release_line)
    if project_root is None:
        output("This directory is not a project, so only the user-wide setup applies.")
    if registry_note:
        output(registry_note)
    discovered = discover_installations(home, registry, project_root)
    home_resolved = home.resolve(strict=False)
    project_resolved = (
        project_root.resolve(strict=False) if project_root is not None else None
    )
    installations = [
        item
        for item in discovered
        if item.kind in {"user", "legacy-user"}
        or item.root.resolve(strict=False) == home_resolved
        or (
            project_resolved is not None
            and item.root.resolve(strict=False) == project_resolved
        )
    ]
    _show_setup_status(
        output, installations, available, home, project_root, registry, released
    )

    reviewed_updates: set[Path] = set()
    user_items = [
        item for item in installations if item.kind in {"user", "legacy-user"}
    ]
    user_scope = next((item for item in user_items if item.kind == "user"), None)
    project_scope = next(
        (
            item
            for item in installations
            if item.kind == "project"
            and project_resolved is not None
            and item.root.resolve(strict=False) == project_resolved
        ),
        None,
    )
    user_installed = bool(user_items)
    user_needs_migration = any(
        _is_previous_managed_user(item) for item in installations
    )
    outdated = _outdated_installations(installations, available, reviewed_updates)
    removable = [item for item in installations if item.kind != "unmanaged"]
    missing_user = [
        tool for tool in TOOLS if user_scope is not None and tool not in user_scope.tools
    ]
    missing_project = [
        tool
        for tool in TOOLS
        if project_scope is not None and tool not in project_scope.tools
    ]
    notice_scopes = [
        scope
        for scope in (user_scope, project_scope)
        if scope is not None and scope.tools
    ]

    # One entry per change; a trailing "..." means a question follows.
    actions: list[tuple[str, str]] = []
    if outdated:
        more = "..." if len(outdated) > 1 else ""
        actions.append((f"update to {available.baseline_id}{more}", "update"))
    user_action_index = len(actions) + 1
    if any(item.kind == "legacy-user" for item in user_items):
        actions.append(("switch your user account to a managed copy...", "user"))
    elif user_scope is None or not user_scope.tools:
        actions.append(("install for your user account...", "user"))
    elif missing_user:
        actions.append((_add_label(missing_user, ""), "user_add"))
    if project_root is not None:
        if project_scope is None or not project_scope.tools:
            actions.append(
                (f"install in project {display_path(project_root)}...", "project")
            )
        elif missing_project:
            actions.append(
                (_add_label(missing_project, " in project"), "project_add")
            )
    for scope, where, key in (
        (user_scope, "", "user_notice"),
        (project_scope, " in project", "project_notice"),
    ):
        if (
            scope is not None
            and scope.tools
            and len(_session_notice_tools(scope)) < len(scope.tools)
        ):
            actions.append((f"enable session notice{where}...", key))
    if any(_session_notice_tools(scope) for scope in notice_scopes):
        if update_check_enabled(registry):
            actions.append(("disable update notice", "notice_off"))
        else:
            actions.append(("enable update notice...", "notice_on"))
    if len(removable) == 1:
        actions.append((f"remove from {_scope_name(removable[0])}...", "remove"))
    elif removable:
        actions.append(("remove...", "remove"))
    actions.append(("exit", "exit"))
    output("\nWhat would you like to do?")
    for number, (label, _key) in enumerate(actions, 1):
        output(f"  {number}. {label}")
    valid_choices = {str(number) for number in range(1, len(actions) + 1)}
    exit_choice = str(len(actions))
    # A tracked update keeps its former default, while an unrecorded file still
    # gets a separate default-no replacement question. Otherwise offer user-wide
    # setup only while it is missing or still needs migration. Pressing Enter
    # must never install into the current project implicitly.
    if outdated:
        default_choice = "1"
    elif not user_installed or user_needs_migration:
        default_choice = str(user_action_index)
    else:
        default_choice = exit_choice
    choice = ""
    for _ in range(3):
        choice = _read_answer(input_fn, f"Choice [{default_choice}]: ") or default_choice
        if choice in valid_choices:
            break
        output(f"Invalid selection. Choose {', '.join(sorted(valid_choices))}.")
    else:
        output("Invalid selection; no additional changes made.")
        return 2

    action_changed = False
    action_incomplete = False
    message: str | None = None
    chosen = actions[int(choice) - 1][1]
    if chosen == "update":
        action_changed, action_incomplete, message = _update_interactively(
            outdated, available, registry, reviewed_updates, input_fn, output
        )
    elif chosen == "user":
        action_changed, action_incomplete = _install_user_interactively(
            home, registry, available, reviewed_updates, input_fn, output
        )
    elif chosen == "user_add" and user_scope is not None:
        action_changed, action_incomplete, message = _add_tools_interactively(
            user_scope, missing_user, available, registry, input_fn, output
        )
    elif chosen == "project" and project_root is not None:
        action_changed, action_incomplete = _install_project_interactively(
            home,
            registry,
            available,
            reviewed_updates,
            input_fn,
            output,
            project_root,
        )
    elif chosen == "project_add" and project_scope is not None:
        action_changed, action_incomplete, message = _add_tools_interactively(
            project_scope, missing_project, available, registry, input_fn, output
        )
    elif chosen in {"user_notice", "project_notice"}:
        scope = user_scope if chosen == "user_notice" else project_scope
        action_incomplete, action_changed = _offer_session_notice(
            scope, input_fn, output
        )
        if action_changed and not update_check_enabled(registry):
            _offer_update_notice(registry, input_fn, output)
    elif chosen == "notice_on":
        action_changed = _offer_update_notice(registry, input_fn, output)
        message = "Update notice enabled."
    elif chosen == "notice_off":
        _set_update_notice(registry, False)
        action_changed = True
        message = "Update notice disabled."
    elif chosen == "remove":
        removed = _remove_interactively(registry, removable, input_fn, output)
        action_changed = bool(removed)
        message = f"Removed from {_scope_names(removed)}."

    if action_changed:
        _save_setup_registry(state_path, registry, registry_writable, output)
    if chosen == "exit":
        output("No changes made.")
    elif action_incomplete:
        output("\nSetup finished with unresolved items.")
        return 2
    elif action_changed:
        output(f"\n{message or 'Setup complete.'}")
    else:
        output("\nNo additional changes made.")
    return 0


def installation_status(
    *,
    home: Path,
    output: Callable[[str], None] = print,
    check_online: bool = True,
    state_path: Path | None = None,
    current_root: Path | None = None,
) -> int:
    available, _note, released = latest_available(check_online)
    state_path = state_path or registry_path(home)
    registry, registry_writable, registry_note = load_registry_with_previous(
        home, state_path
    )
    if registry_writable:
        cache_release_check(state_path, registry, released)
    current_root = (current_root or Path.cwd()).resolve()
    if current_root == Path(current_root.anchor) or not current_root.is_dir():
        raise ValueError("current project must be an existing non-root directory")

    output("AI Secure Coding Baseline status")
    release_line = _release_line(available, released, check_online)
    if release_line:
        output(release_line)
    if registry_note:
        output(registry_note)
    installations = discover_installations(home, registry, current_root)
    _show_setup_status(
        output, installations, available, home, current_root, registry, released
    )
    return 0


def uninstall(
    *,
    home: Path,
    root: Path,
    user: bool,
    output: Callable[[str], None] = print,
    state_path: Path | None = None,
) -> int:
    """Remove one scope without asking; the guided setup offers a choice."""
    state_path = state_path or registry_path(home)
    registry, writable, note = load_registry_with_previous(home, state_path)
    if note:
        output(note)
    if user:
        found = [item for item in scan_user(home, registry.get("user")) if item.kind
                 in {"user", "legacy-user"}]
    else:
        projects = registry.get("projects")
        entry = projects.get(str(root.resolve())) if isinstance(projects, dict) else None
        item = scan_project(root, entry if isinstance(entry, dict) else {})
        found = [item] if item else []
    if not found:
        output("Nothing installed here.")
        return 1
    removed = False
    for item in found:
        report: list[str] = []
        if remove_installation(item, report):
            forget_installation(registry, item)
            removed = True
        for line in report:
            output(line)
    if removed and writable:
        projects = registry.get("projects")
        empty = registry.get("user") is None and not (
            projects if isinstance(projects, dict) else {}
        )
        if empty and state_path.is_file() and not state_path.is_symlink():
            state_path.unlink()
            output(f"removed {state_path}")
        else:
            save_registry(state_path, registry)
    return 0 if removed else 1


def _register_noninteractive(
    registry: dict[str, object], root: Path, home: Path | None
) -> None:
    available = bundled_baseline()
    if home is None:
        installation = scan_project(root, {})
    else:
        matches = [item for item in scan_user(home, {}) if item.kind == "user"]
        installation = matches[0] if matches else None
    if installation:
        trusted = installation.baseline.digest == available.digest
        record_installation(registry, installation, trusted=trusted)


def _interactive_check_online(offline: bool) -> bool:
    """Only a checkout may replace its bundle with a release fetched at runtime."""
    return not offline and LOCAL_ORIGIN != "installed copy"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tools", nargs="*", help=f"any of {', '.join(TOOLS)}; default is all"
    )
    parser.add_argument(
        "--user", action="store_true", help="install for this user instead of a project"
    )
    parser.add_argument(
        "--into",
        type=Path,
        default=Path.cwd(),
        help="project directory (default: the current one)",
    )
    parser.add_argument(
        "--interactive", action="store_true", help="run the guided setup and updater"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="show installation status without changing an installation",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="skip the release check during setup or status",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove what this installer placed for a project or, with --user, this user",
    )
    parser.add_argument(
        "--refresh-update-cache",
        action="store_true",
        help="look up the published release for the startup hook, if setup allowed it",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="fetch the signed release bundle, verify it, and run its guided setup",
    )
    parser.add_argument(
        "--session-switch", action="store_true",
        help="opt in to AISCB_DISABLE=1 for new Claude/Codex sessions; migrate managed links only",
    )
    args = parser.parse_args(argv)

    if args.session_switch and (args.interactive or args.status or args.offline
                               or args.uninstall or args.refresh_update_cache or args.update):
        parser.error("--session-switch takes only claude/codex, --user or --into")

    if args.uninstall:
        if args.tools or args.status or args.interactive or args.offline or args.update:
            parser.error("--uninstall takes only --user or --into")
        return uninstall(home=Path.home(), root=args.into, user=args.user)

    if args.refresh_update_cache:
        if (args.tools or args.user or args.status or args.interactive
                or args.offline or args.uninstall or args.update):
            parser.error("--refresh-update-cache takes no other arguments")
        return refresh_update_cache(home=Path.home())

    if args.update:
        if args.tools or args.user or args.status or args.interactive or args.offline:
            parser.error("--update takes no other arguments")
        if not sys.stdin.isatty():
            parser.error("the update runs the guided setup and needs a terminal")
        try:
            return release_update()
        except (OSError, ValueError):
            print("Update stopped after an error; nothing was changed.", file=sys.stderr)
            return 1

    if args.interactive:
        if args.tools or args.user or args.status:
            parser.error(
                "--interactive cannot be combined with tools, --user, or --status"
            )
        if not sys.stdin.isatty():
            parser.error(
                "the guided setup needs a terminal; run it from one, or install "
                "without --interactive"
            )
        try:
            check_online = _interactive_check_online(args.offline)
            return interactive_setup(home=Path.home(), check_online=check_online)
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.", file=sys.stderr)
            return 130
        except (OSError, ValueError):
            print("Setup stopped after an error; review the reported files.", file=sys.stderr)
            return 1

    if args.status:
        if args.tools or args.user:
            parser.error("--status cannot be combined with tools or --user")
        try:
            return installation_status(
                home=Path.home(),
                check_online=not args.offline,
                current_root=args.into,
            )
        except (OSError, ValueError):
            print("Status check stopped after an error.", file=sys.stderr)
            return 1

    if args.offline:
        parser.error("--offline is only valid with --interactive or --status")
    tools = list(args.tools) or (["claude", "codex"] if args.session_switch else list(TOOLS))
    unknown = [tool for tool in tools if tool not in TOOLS]
    if unknown:
        parser.error(f"unknown tool {unknown[0]!r}; choose from {', '.join(TOOLS)}")
    if args.session_switch and "copilot" in tools:
        parser.error("--session-switch supports claude and codex only")

    root = args.into.resolve()
    if not args.user and (root == Path(root.anchor) or not root.is_dir()):
        parser.error("--into must be an existing non-root directory")
    home = Path.home() if args.user else None
    action = install_session_switch if args.session_switch else install
    report = action(tools, root, home)
    for line in report:
        print(line)
    if args.session_switch and any(line.startswith("blocked") for line in report):
        return 1

    state_path = registry_path(Path.home())
    registry, writable, note = load_registry_with_previous(Path.home(), state_path)
    if note:
        print(note, file=sys.stderr)
    if writable:
        _register_noninteractive(registry, root, home)
        save_registry(state_path, registry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

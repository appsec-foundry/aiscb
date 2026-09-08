#!/usr/bin/env python3
"""Install a built release into a versioned directory and switch to it in one step.

    install.py install <bundle-dir> --manifest-sha256 <hex> [--root DIR]
    install.py rollback [--root DIR]
    install.py status   [--root DIR]
    install.py uninstall [--root DIR]

The manifest digest arrives through a channel other than the bundle, for
example the device-management job or the package that carries this command.
Nothing is copied before the manifest and every listed file have been
verified. Releases are immutable: a version that is already installed is never
overwritten, and ``current`` moves to the new release in one rename so a
session either sees the old release or the new one.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".local" / "share" / "aiscb"
RECORD = "installed.json"
MANIFEST_KEYS = {"bundle", "overlay", "aiscb", "aiscb_sha256", "release_dir", "files"}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*-\d+\.\d+\.\d+$")
HEX_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST_BYTES = 1024 * 1024


class InstallError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(rel: str) -> Path:
    parts = rel.split("/")
    if (not rel or rel.startswith("/") or "\\" in rel
            or any(part in ("", ".", "..") for part in parts)):
        raise InstallError(f"refusing manifest path {rel!r}")
    return Path(*parts)


def read_manifest(bundle: Path, expected: str) -> dict:
    expected = expected.lower()
    if not HEX_RE.match(expected):
        raise InstallError("the manifest digest must be 64 hex characters")
    path = bundle / "manifest.json"
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise InstallError("manifest.json is missing or too large")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise InstallError("manifest.json does not match the expected digest")
    try:
        manifest = json.loads(data)
    except ValueError as exc:
        raise InstallError(f"manifest.json is not valid JSON: {exc}") from None
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise InstallError(f"manifest.json must contain exactly {sorted(MANIFEST_KEYS)}")
    for key in ("bundle", "overlay", "aiscb"):
        if not isinstance(manifest[key], str) or not ID_RE.match(manifest[key]):
            raise InstallError(f"manifest {key} is not a valid id")
    if not isinstance(manifest["aiscb_sha256"], str) or not HEX_RE.match(manifest["aiscb_sha256"]):
        raise InstallError("manifest aiscb_sha256 is not a digest")
    if not isinstance(manifest["release_dir"], str) or not manifest["release_dir"]:
        raise InstallError("manifest release_dir is missing")
    files = manifest["files"]
    if not isinstance(files, dict) or not files:
        raise InstallError("manifest lists no files")
    for rel, entry in files.items():
        safe_relative(rel)
        if (not isinstance(entry, dict) or set(entry) != {"size", "sha256"}
                or not isinstance(entry["size"], int) or entry["size"] < 0
                or not isinstance(entry["sha256"], str) or not HEX_RE.match(entry["sha256"])):
            raise InstallError(f"manifest entry for {rel} is malformed")
    if "manifest.json" in files:
        raise InstallError("manifest.json must not list itself")
    return manifest


def verify_files(bundle: Path, manifest: dict) -> None:
    for rel, entry in manifest["files"].items():
        path = bundle / safe_relative(rel)
        if not path.is_file() or path.is_symlink():
            raise InstallError(f"{rel} is missing from the bundle")
        if path.stat().st_size != entry["size"]:
            raise InstallError(f"{rel} has an unexpected size")
        if sha256_file(path) != entry["sha256"]:
            raise InstallError(f"{rel} does not match its recorded digest")


def read_record(root: Path) -> dict:
    path = root / RECORD
    if not path.exists():
        return {"current": None, "previous": None, "releases": {}}
    try:
        record = json.loads(path.read_bytes())
    except ValueError as exc:
        raise InstallError(f"{RECORD} is not valid JSON: {exc}") from None
    if (not isinstance(record, dict) or set(record) != {"current", "previous", "releases"}
            or not isinstance(record["releases"], dict)):
        raise InstallError(f"{RECORD} has an unexpected shape")
    return record


def write_record(root: Path, record: dict) -> None:
    data = json.dumps(record, indent=2).encode("utf-8") + b"\n"
    tmp = root / f"{RECORD}.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, root / RECORD)


def switch_current(root: Path, bundle_id: str) -> None:
    link = root / "current"
    tmp = root / "current.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(Path("releases") / bundle_id, tmp)
    os.replace(tmp, link)


def install(bundle: Path, manifest_sha256: str, root: Path = DEFAULT_ROOT) -> dict:
    manifest = read_manifest(bundle, manifest_sha256)
    bundle_id = manifest["bundle"]
    expected_dir = (root / "releases" / bundle_id).resolve()
    if Path(manifest["release_dir"]).resolve() != expected_dir:
        raise InstallError(f"bundle was built for {manifest['release_dir']}; "
                           f"its generated paths would not resolve under {root}")
    verify_files(bundle, manifest)

    releases = root / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    target = releases / bundle_id
    if target.exists() or target.is_symlink():
        raise InstallError(f"{bundle_id} is already installed; releases are immutable")
    staging = releases / f".staging-{bundle_id}"
    if staging.exists():
        shutil.rmtree(staging)
    try:
        for rel in manifest["files"]:
            destination = staging / safe_relative(rel)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle / safe_relative(rel), destination)
        shutil.copyfile(bundle / "manifest.json", staging / "manifest.json")
        os.rename(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    record = read_record(root)
    switch_current(root, bundle_id)
    record = {
        "current": bundle_id,
        "previous": record["current"],
        "releases": {**record["releases"], bundle_id: sorted(manifest["files"])},
    }
    write_record(root, record)
    return record


def rollback(root: Path = DEFAULT_ROOT) -> dict:
    record = read_record(root)
    previous = record["previous"]
    if not previous or not (root / "releases" / previous).is_dir():
        raise InstallError("no previous release to roll back to")
    switch_current(root, previous)
    record = {"current": previous, "previous": record["current"],
              "releases": record["releases"]}
    write_record(root, record)
    return record


def drift(root: Path, bundle_id: str) -> list[str]:
    release = root / "releases" / bundle_id
    manifest_path = release / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json missing"]
    try:
        manifest = json.loads(manifest_path.read_bytes())
        files = manifest["files"]
    except (ValueError, KeyError, TypeError):
        return ["manifest.json unreadable"]
    problems = []
    for rel, entry in files.items():
        path = release / safe_relative(rel)
        if not path.is_file() or path.stat().st_size != entry["size"] \
                or sha256_file(path) != entry["sha256"]:
            problems.append(rel)
    return problems


def status(root: Path = DEFAULT_ROOT) -> tuple[list[str], bool]:
    record = read_record(root)
    current = record["current"]
    lines = [f"root:     {root}", f"current:  {current or '-'}",
             f"previous: {record['previous'] or '-'}"]
    if not current:
        return lines, True
    link = root / "current"
    if not link.is_symlink() or os.readlink(link) != str(Path("releases") / current):
        lines.append("current link does not point at the recorded release")
        return lines, False
    problems = drift(root, current)
    if problems:
        lines.append("drift:    " + ", ".join(problems))
        return lines, False
    lines.append("files:    match the manifest")
    return lines, True


def uninstall(root: Path = DEFAULT_ROOT) -> list[str]:
    record = read_record(root)
    removed = []
    for bundle_id in record["releases"]:
        release = root / "releases" / bundle_id
        if release.is_dir():
            shutil.rmtree(release)
            removed.append(str(release))
    link = root / "current"
    if link.is_symlink():
        link.unlink()
        removed.append(str(link))
    record_path = root / RECORD
    if record_path.exists():
        record_path.unlink()
        removed.append(str(record_path))
    releases = root / "releases"
    if releases.is_dir() and not any(releases.iterdir()):
        releases.rmdir()
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    install_cmd = commands.add_parser("install")
    install_cmd.add_argument("bundle", type=Path)
    install_cmd.add_argument("--manifest-sha256", required=True)
    for name in ("rollback", "status", "uninstall"):
        commands.add_parser(name)
    args = parser.parse_args(argv)
    root = args.root.expanduser()
    try:
        if args.command == "install":
            record = install(args.bundle, args.manifest_sha256, root)
            print(f"installed {record['current']}; current now points at it")
        elif args.command == "rollback":
            record = rollback(root)
            print(f"rolled back to {record['current']}")
        elif args.command == "status":
            lines, healthy = status(root)
            print("\n".join(lines))
            return 0 if healthy else 1
        else:
            for path in uninstall(root):
                print(f"removed {path}")
    except (InstallError, OSError) as exc:
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

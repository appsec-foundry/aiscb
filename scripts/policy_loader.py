#!/usr/bin/env python3
"""Read a pinned local policy package; return complete dependency-closed modules."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

MAX_BYTES = 1024 * 1024
ID = re.compile(r"[a-z][a-z0-9-]*:[a-z][a-z0-9-]*")
DIGEST = re.compile(r"[0-9a-f]{64}")


def pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError(f"duplicate key: {key}")
        value[key] = item
    return value


def read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"not a regular policy file: {path.name}")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("policy file exceeds size limit")
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(root, name):
    if (not isinstance(name, str) or not name or "\\" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
            or Path(name).is_absolute()):
        raise ValueError("unsafe policy path")
    path = root / name
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("symlink in policy path")
    return path


def load_package(root, expected):
    if not isinstance(expected, str) or not DIGEST.fullmatch(expected):
        raise ValueError("a trusted package digest is required")
    raw = read(root / "policy.json")
    if digest(raw) != expected:
        raise ValueError("policy manifest digest mismatch")
    package = json.loads(raw, object_pairs_hook=pairs)
    if (not isinstance(package, dict)
            or set(package) != {"schema", "release", "core", "overlay", "modules", "files"}
            or package["schema"] != 1 or not isinstance(package["release"], str)
            or not isinstance(package["files"], dict)
            or not isinstance(package["modules"], list)):
        raise ValueError("invalid policy schema")
    contents = {}
    if len(package["files"]) > 256:
        raise ValueError("too many policy files")
    for name, entry in package["files"].items():
        if (not isinstance(entry, dict) or set(entry) != {"size", "sha256"}
                or type(entry["size"]) is not int or not 0 < entry["size"] <= MAX_BYTES
                or not isinstance(entry["sha256"], str)
                or not DIGEST.fullmatch(entry["sha256"])):
            raise ValueError("invalid artifact metadata")
        content = read(safe_path(root, name))
        if len(content) != entry["size"] or digest(content) != entry["sha256"]:
            raise ValueError(f"policy artifact mismatch: {name}")
        contents[name] = content.decode("utf-8")
    if package["core"] not in contents or (package["overlay"] is not None
                                           and package["overlay"] not in contents):
        raise ValueError("missing core or overlay")
    modules = {}
    artifacts = {package["core"], package["overlay"]}
    for entry in package["modules"]:
        if (not isinstance(entry, dict)
                or set(entry) != {"id", "artifact", "trigger", "paths", "requires", "blueprints"}
                or not isinstance(entry["id"], str) or not ID.fullmatch(entry["id"])
                or entry["id"] in modules or entry["artifact"] not in contents
                or entry["artifact"] in artifacts
                or not isinstance(entry["trigger"], str) or not entry["trigger"].strip()):
            raise ValueError("invalid or colliding policy module")
        for key in ("paths", "requires", "blueprints"):
            if (not isinstance(entry[key], list)
                    or any(not isinstance(item, str) for item in entry[key])):
                raise ValueError(f"invalid module {key}")
        if any(name not in contents for name in entry["blueprints"]):
            raise ValueError("missing blueprint")
        if f"`module-id: {entry['id']}`" not in contents[entry["artifact"]]:
            raise ValueError("module body identity mismatch")
        artifacts.add(entry["artifact"])
        modules[entry["id"]] = entry
    closure(modules, list(modules))
    return package, contents, modules


def closure(modules, selected):
    ordered, visiting, visited = [], set(), set()

    def visit(name):
        if name not in modules:
            raise ValueError(f"unknown module: {name}")
        if name in visiting:
            raise ValueError("module dependency cycle")
        if name in visited:
            return
        visiting.add(name)
        for dependency in modules[name]["requires"]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in selected:
        visit(name)
    return ordered


def render(root, expected, selected):
    package, contents, modules = load_package(root, expected)
    result, blueprints = [], set()
    for name in closure(modules, selected):
        entry = modules[name]
        result.append(f"Verified {name}; release {package['release']}\n\n"
                      + contents[entry["artifact"]])
        for blueprint in entry["blueprints"]:
            if blueprint not in blueprints:
                result.append(f"Blueprint values: {blueprint}\n\n" + contents[blueprint])
                blueprints.add(blueprint)
    return "\n\n".join(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digest", required=True)
    parser.add_argument("ids", nargs="+")
    args = parser.parse_args()
    try:
        output = render(Path(__file__).resolve().parent, args.digest, args.ids)
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(f"Policy loading refused: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

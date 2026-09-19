#!/usr/bin/env python3
"""Validate modular aiscb sources and build the eager compatibility file."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath

from policy_loader import safe_path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "baseline"
CATALOG = SOURCE_ROOT / "catalog.json"

BASELINE_ID = "aiscb-0.1.16"
VERSION = "0.1.16"
EAGER = ROOT / "dist" / "dev" / BASELINE_ID / "secure-coding-baseline.md"
MODULE_ID = re.compile(r"aiscb:[a-z][a-z0-9-]*")
RULE_ID = re.compile(r"aiscb-[A-Z][A-Z0-9]*-\d{3}")
RULE_BULLET = re.compile(r"^- \*\*\[(aiscb-[^\]]+)\] [^:]+:\*\*")
BASELINE_LINE = re.compile(r"^`baseline-id: ([^`]+)`", re.MULTILINE)
MODULE_LINE = re.compile(r"^`module-id: ([^`]+)`", re.MULTILINE)

TOP_KEYS = {"schema", "baseline_id", "core", "modules"}
CORE_KEYS = {"file", "rules", "size", "sha256"}
MODULE_KEYS = {
    "id", "publisher", "version", "file", "trigger", "paths", "requires",
    "rules", "size", "sha256",
}


class Invalid(ValueError):
    """A modular source or catalog violates the release contract."""


def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise Invalid(f"duplicate catalog key: {key}")
        result[key] = value
    return result


def load_catalog(path: Path | None = None) -> dict:
    try:
        value = json.loads((path or CATALOG).read_text(encoding="utf-8"),
                           object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Invalid(f"cannot read catalog: {exc}") from exc
    if not isinstance(value, dict):
        raise Invalid("catalog must be an object")
    if set(value) != TOP_KEYS:
        raise Invalid(f"catalog keys must be exactly {sorted(TOP_KEYS)}")
    if value["schema"] != 1 or value["baseline_id"] != BASELINE_ID:
        raise Invalid(f"catalog must describe {BASELINE_ID} with schema 1")
    if not isinstance(value["core"], dict) or set(value["core"]) != CORE_KEYS:
        raise Invalid(f"core keys must be exactly {sorted(CORE_KEYS)}")
    if not isinstance(value["modules"], list) or not value["modules"]:
        raise Invalid("catalog modules must be a non-empty list")
    return value


def source_path(relative: object, *, module: bool, root: Path | None = None) -> Path:
    if not isinstance(relative, str):
        raise Invalid("artifact path must be a string")
    logical = PurePosixPath(relative)
    expected_parent = PurePosixPath("modules") if module else PurePosixPath(".")
    if (logical.is_absolute() or ".." in logical.parts or logical.suffix != ".md"
            or (module and logical.parent != expected_parent)
            or (not module and logical != PurePosixPath("aiscb-core.md"))):
        raise Invalid(f"unsafe or unexpected artifact path: {relative!r}")
    root = root or SOURCE_ROOT
    path = root.joinpath(*logical.parts)
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise Invalid(f"artifact path contains a symlink: {relative}")
        if part == root:
            break
    if not path.is_file():
        raise Invalid(f"artifact must be a regular file: {relative}")
    return path


def text_and_bytes(path: Path) -> tuple[str, bytes]:
    raw = path.read_bytes()
    if not raw or len(raw) > 128 * 1024:
        raise Invalid(f"artifact has invalid size: {path.name}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Invalid(f"artifact is not UTF-8: {path.name}") from exc
    if not text.endswith("\n"):
        raise Invalid(f"artifact must end with a newline: {path.name}")
    return text, raw


def rules(text: str, where: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        if line.startswith("- **["):
            match = RULE_BULLET.match(line)
            if not match or not RULE_ID.fullmatch(match.group(1)):
                raise Invalid(f"invalid rule-group bullet in {where}: {line}")
            found.append(match.group(1))
    if not found:
        raise Invalid(f"artifact has no rule groups: {where}")
    if len(found) != len(set(found)):
        raise Invalid(f"artifact repeats a rule ID: {where}")
    return found


def string_list(value: object, name: str) -> list[str]:
    if (not isinstance(value, list)
            or any(not isinstance(item, str) or not item for item in value)):
        raise Invalid(f"{name} must be a list of non-empty strings")
    return value


def validate(root: Path | None = None) -> tuple[dict, list[tuple[dict, bytes]], bytes]:
    source_root = root or SOURCE_ROOT
    catalog = load_catalog(source_root / "catalog.json" if root else None)
    core = catalog["core"]
    core_path = source_path(core["file"], module=False, root=source_root)
    core_text, core_raw = text_and_bytes(core_path)
    identifiers = BASELINE_LINE.findall(core_text)
    if identifiers != [BASELINE_ID]:
        raise Invalid(f"core must declare exactly {BASELINE_ID}")
    actual_core_rules = rules(core_text, "core")
    if string_list(core["rules"], "core rules") != actual_core_rules:
        raise Invalid("core rule list does not match aiscb-core.md")

    seen_modules: set[str] = set()
    seen_rules = set(actual_core_rules)
    modules: list[tuple[dict, bytes]] = []
    known_ids: list[str] = []
    for index, module in enumerate(catalog["modules"]):
        if not isinstance(module, dict) or set(module) != MODULE_KEYS:
            raise Invalid(f"module {index} keys must be exactly {sorted(MODULE_KEYS)}")
        module_id = module["id"]
        if not isinstance(module_id, str) or not MODULE_ID.fullmatch(module_id):
            raise Invalid(f"invalid module id: {module_id!r}")
        if module_id in seen_modules:
            raise Invalid(f"duplicate module id: {module_id}")
        seen_modules.add(module_id)
        known_ids.append(module_id)
        if module["publisher"] != "aiscb" or module["version"] != VERSION:
            raise Invalid(f"module {module_id} has incompatible publisher or version")
        if not isinstance(module["trigger"], str) or not module["trigger"].strip():
            raise Invalid(f"module {module_id} needs a semantic trigger")
        string_list(module["paths"], f"{module_id} paths")
        requires = string_list(module["requires"], f"{module_id} requires")
        if module_id in requires:
            raise Invalid(f"module {module_id} requires itself")

        path = source_path(module["file"], module=True, root=source_root)
        text, raw = text_and_bytes(path)
        if MODULE_LINE.findall(text) != [module_id]:
            raise Invalid(f"{module['file']} must declare exactly {module_id}")
        if BASELINE_LINE.search(text):
            raise Invalid(f"module declares a baseline ID: {module['file']}")
        actual_rules = rules(text, module_id)
        if string_list(module["rules"], f"{module_id} rules") != actual_rules:
            raise Invalid(f"rule list does not match {module['file']}")
        repeated = seen_rules.intersection(actual_rules)
        if repeated:
            raise Invalid(f"rule IDs appear in more than one artifact: {sorted(repeated)}")
        seen_rules.update(actual_rules)
        modules.append((module, raw))

    for module, _ in modules:
        unknown = sorted(set(module["requires"]) - set(known_ids))
        if unknown:
            raise Invalid(f"module {module['id']} requires unknown modules: {unknown}")

    dependencies = {module["id"]: module["requires"] for module, _ in modules}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_id: str) -> None:
        if module_id in visiting:
            raise Invalid(f"module dependency cycle includes {module_id}")
        if module_id in visited:
            return
        visiting.add(module_id)
        for required in dependencies[module_id]:
            visit(required)
        visiting.remove(module_id)
        visited.add(module_id)

    for module_id in known_ids:
        visit(module_id)

    listed_files = {source_root / module["file"] for module, _ in modules}
    actual_files = set((source_root / "modules").glob("*.md"))
    if listed_files != actual_files:
        missing = sorted(str(path.relative_to(source_root))
                         for path in listed_files - actual_files)
        unlisted = sorted(str(path.relative_to(source_root))
                          for path in actual_files - listed_files)
        raise Invalid(f"module inventory mismatch; missing={missing}, unlisted={unlisted}")

    eager = core_raw.rstrip() + b"\n"
    for _, raw in modules:
        eager += b"\n" + raw.rstrip() + b"\n"
    if BASELINE_LINE.findall(eager.decode("utf-8")) != [BASELINE_ID]:
        raise Invalid("eager artifact would not contain exactly one baseline ID")
    eager_rules = rules(eager.decode("utf-8"), "eager")
    if set(eager_rules) != seen_rules or len(eager_rules) != len(seen_rules):
        raise Invalid("eager artifact does not contain every rule exactly once")
    return catalog, [(core, core_raw), *modules], eager


def metadata(raw: bytes) -> tuple[int, str]:
    return len(raw), hashlib.sha256(raw).hexdigest()


def render_catalog(catalog: dict, artifacts: list[tuple[dict, bytes]]) -> bytes:
    for entry, raw in artifacts:
        entry["size"], entry["sha256"] = metadata(raw)
    return (json.dumps(catalog, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def stale_outputs() -> list[str]:
    catalog, artifacts, eager = validate()
    failures = []
    if CATALOG.read_bytes() != render_catalog(catalog, artifacts):
        failures.append("baseline/catalog.json metadata is stale")
    if EAGER.exists() and EAGER.read_bytes() != eager:
        failures.append("secure-coding-baseline.md is not the generated eager artifact")
    return failures


def write_complete(raw: bytes) -> None:
    """Write only the bounded development path, without following links."""
    target = safe_path(ROOT, EAGER.relative_to(ROOT).as_posix())
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".baseline-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        catalog, artifacts, eager = validate()
        rendered_catalog = render_catalog(catalog, artifacts)
        if args.write:
            CATALOG.write_bytes(rendered_catalog)
            write_complete(eager)
            print(f"wrote {EAGER.relative_to(ROOT)} and {CATALOG.relative_to(ROOT)}")
            return 0
        failures = stale_outputs()
        if failures:
            raise Invalid("; ".join(failures) + "; run scripts/build_baseline.py --write")
    except (Invalid, OSError) as exc:
        print(f"modular baseline: {exc}", file=sys.stderr)
        return 1
    print("modular baseline: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

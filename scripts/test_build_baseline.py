#!/usr/bin/env python3
"""Mutation checks for the modular baseline builder."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "build_baseline", ROOT / "scripts" / "build_baseline.py")
assert SPEC and SPEC.loader
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)

checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        raise AssertionError(message)
    print(f"ok   {message}")


@contextmanager
def fixture():
    old = BUILD.SOURCE_ROOT, BUILD.CATALOG, BUILD.EAGER
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(ROOT / "baseline", root / "baseline")
        (root / "secure-coding-baseline.md").write_bytes(BUILD.validate()[2])
        BUILD.SOURCE_ROOT = root / "baseline"
        BUILD.CATALOG = BUILD.SOURCE_ROOT / "catalog.json"
        BUILD.EAGER = root / "secure-coding-baseline.md"
        try:
            yield root
        finally:
            BUILD.SOURCE_ROOT, BUILD.CATALOG, BUILD.EAGER = old


def catalog() -> dict:
    return json.loads(BUILD.CATALOG.read_text(encoding="utf-8"))


def write_catalog(value: dict) -> None:
    BUILD.CATALOG.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def rejected(change, expected: str) -> bool:
    with fixture() as root:
        change(root)
        try:
            BUILD.stale_outputs()
        except BUILD.Invalid as exc:
            return expected in str(exc)
        return False


check(not BUILD.stale_outputs(), "current modular sources and eager artifact agree")


def duplicate_id(_root: Path) -> None:
    value = catalog()
    value["modules"][1]["id"] = value["modules"][0]["id"]
    write_catalog(value)


check(rejected(duplicate_id, "duplicate module id"), "duplicate module IDs are rejected")


def wrong_version(_root: Path) -> None:
    value = catalog()
    value["modules"][0]["version"] = "0.1.15"
    write_catalog(value)


check(rejected(wrong_version, "incompatible publisher or version"),
      "cross-release modules are rejected")


def unknown_dependency(_root: Path) -> None:
    value = catalog()
    value["modules"][0]["requires"] = ["aiscb:not-present"]
    write_catalog(value)


check(rejected(unknown_dependency, "requires unknown modules"),
      "unknown module dependencies are rejected")


def dependency_cycle(_root: Path) -> None:
    value = catalog()
    first, second = value["modules"][:2]
    first["requires"] = [second["id"]]
    second["requires"] = [first["id"]]
    write_catalog(value)


check(rejected(dependency_cycle, "dependency cycle"),
      "module dependency cycles are rejected")


def repeated_rule(root: Path) -> None:
    target = root / "baseline" / "modules" / "aiscb-data-handling.md"
    target.write_text(target.read_text().replace("aiscb-ERRORS-001",
                                                  "aiscb-AUTH-001", 1))
    value = catalog()
    next(m for m in value["modules"] if m["id"] == "aiscb:data-handling")["rules"][0] = "aiscb-AUTH-001"
    write_catalog(value)


check(rejected(repeated_rule, "more than one artifact"),
      "rule IDs repeated across modules are rejected")


def unlisted_module(root: Path) -> None:
    (root / "baseline" / "modules" / "extra.md").write_text(
        "# Extra\n\n`module-id: aiscb:extra`.\n\n"
        "## Extra\n\n- **[aiscb-EXTRA-001] Extra:** Rule.\n")


check(rejected(unlisted_module, "unlisted"), "unlisted module files are rejected")

with fixture() as root:
    module = root / "baseline" / "modules" / "aiscb-web.md"
    module.write_text(module.read_text() + "\nChanged.\n")
    failures = BUILD.stale_outputs()
    check(any("metadata is stale" in item for item in failures)
          and any("eager artifact" in item for item in failures),
          "changed module bytes make catalog metadata and eager output stale")

with fixture() as root:
    (root / "secure-coding-baseline.md").write_text("changed\n")
    check(BUILD.stale_outputs() == [
        "secure-coding-baseline.md is not the generated eager artifact"],
        "changed eager output is rejected")

print(f"modular baseline builder: ok ({checks} checks)")
